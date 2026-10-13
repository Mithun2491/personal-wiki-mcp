import "server-only";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { UnauthorizedError } from "@modelcontextprotocol/sdk/client/auth.js";
import type { ApiErrorCode, ConnectionMode } from "@/lib/types";

const CONNECT_TIMEOUT_MS = 15_000;
const CALL_TIMEOUT_MS = 20_000;

export class McpError extends Error {
  constructor(
    readonly code: ApiErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "McpError";
  }
}

let clientPromise: Promise<Client> | null = null;

function config(): { url: string | null; token: string | null } {
  return {
    url: process.env.MCP_SERVER_URL || null,
    token: process.env.MCP_AUTH_TOKEN || null,
  };
}

function detectMode(url: URL): ConnectionMode {
  const host = url.hostname;
  return host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host === "[::1]"
    ? "local"
    : "remote";
}

function sanitizedUrl(url: URL): string {
  const clean = new URL(url.toString());
  clean.username = "";
  clean.password = "";
  return clean.toString();
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new McpError("timeout", "The wiki backend did not respond in time."));
    }, ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err: unknown) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

function isNetworkError(err: unknown): boolean {
  if (err instanceof TypeError) return true;
  if (err instanceof Error) {
    const cause = err.cause as { code?: string } | undefined;
    const code = cause?.code ?? (err as { code?: string }).code;
    return (
      code === "ECONNREFUSED" ||
      code === "ENOTFOUND" ||
      code === "ECONNRESET" ||
      code === "EAI_AGAIN" ||
      err.message.includes("fetch failed")
    );
  }
  return false;
}

function classifyError(err: unknown): McpError {
  if (err instanceof McpError) return err;
  if (
    err instanceof UnauthorizedError ||
    (err instanceof Error &&
      err.name === "StreamableHTTPError" &&
      (err as { code?: number }).code === 401)
  ) {
    return new McpError(
      "unauthorized",
      "The wiki backend rejected the configured credentials.",
    );
  }
  if (
    err instanceof Error &&
    err.name === "StreamableHTTPError" &&
    (err as { code?: number }).code === 404
  ) {
    return new McpError(
      "unreachable",
      "The MCP endpoint was not found. Check MCP_SERVER_URL.",
    );
  }
  if (err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError")) {
    return new McpError("timeout", "The wiki backend did not respond in time.");
  }
  if (isNetworkError(err)) {
    return new McpError(
      "unreachable",
      "The wiki backend is unreachable. Check that it is running.",
    );
  }
  if (err instanceof Error && err.name === "StreamableHTTPError") {
    return new McpError("backend", "The wiki backend returned an unexpected response.");
  }
  return new McpError("backend", "The wiki backend could not complete the request.");
}

export function resetClient(): void {
  const pending = clientPromise;
  clientPromise = null;
  if (pending) {
    void pending.then((client) => client.close()).catch(() => {});
  }
}

async function connectClient(): Promise<Client> {
  const { url: rawUrl, token } = config();
  if (!rawUrl) {
    throw new McpError("config", "MCP_SERVER_URL is not set.");
  }
  if (!token) {
    throw new McpError("config", "MCP_AUTH_TOKEN is not set.");
  }

  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new McpError("config", "MCP_SERVER_URL is not a valid URL.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new McpError("config", "MCP_SERVER_URL must be an http or https URL.");
  }

  const transport = new StreamableHTTPClientTransport(url, {
    requestInit: {
      headers: { Authorization: `Bearer ${token}` },
    },
  });
  const client = new Client({
    name: "personal-knowledge-hub",
    version: "0.1.0",
  });
  await withTimeout(client.connect(transport), CONNECT_TIMEOUT_MS);
  return client;
}

async function getClient(): Promise<Client> {
  if (!clientPromise) {
    clientPromise = connectClient().catch((err: unknown) => {
      clientPromise = null;
      throw err;
    });
  }
  return clientPromise;
}

function extractText(result: unknown): string {
  const content = (result as { content?: unknown }).content;
  const blocks = Array.isArray(content) ? content : [];
  return blocks
    .filter(
      (b): b is { type: "text"; text: string } =>
        typeof b === "object" &&
        b !== null &&
        (b as { type?: unknown }).type === "text" &&
        typeof (b as { text?: unknown }).text === "string",
    )
    .map((b) => b.text)
    .join("\n");
}

export async function callWikiTool(name: string, args: Record<string, unknown>): Promise<string> {
  const client = await getClient();
  let result: Awaited<ReturnType<Client["callTool"]>>;
  try {
    result = await withTimeout(
      client.callTool({ name, arguments: args }),
      CALL_TIMEOUT_MS,
    );
  } catch (err) {
    const classified = classifyError(err);
    if (
      classified.code === "unreachable" ||
      classified.code === "timeout" ||
      classified.code === "backend"
    ) {
      resetClient();
    }
    throw classified;
  }
  const text = extractText(result);
  if (result.isError) {
    throw new McpError("backend", text || "The wiki backend reported an error.");
  }
  return text;
}

export interface BackendProbe {
  connected: boolean;
  configured: boolean;
  mode: ConnectionMode | null;
  url: string | null;
  server: { name: string | null; version: string | null } | null;
  tools: string[];
  error: { code: ApiErrorCode; message: string } | null;
}

export async function probeBackend(): Promise<BackendProbe> {
  const { url: rawUrl, token } = config();
  const configured = Boolean(rawUrl && token);

  let mode: ConnectionMode | null = null;
  let url: string | null = null;
  if (rawUrl) {
    try {
      const parsed = new URL(rawUrl);
      mode = detectMode(parsed);
      url = sanitizedUrl(parsed);
    } catch {
      mode = null;
      url = null;
    }
  }

  if (!configured) {
    return {
      connected: false,
      configured: false,
      mode,
      url,
      server: null,
      tools: [],
      error: {
        code: "config",
        message: "MCP_SERVER_URL and MCP_AUTH_TOKEN must be set in the server environment.",
      },
    };
  }

  try {
    const client = await getClient();
    const tools = await withTimeout(client.listTools(), CALL_TIMEOUT_MS);
    const info = client.getServerVersion();
    return {
      connected: true,
      configured: true,
      mode,
      url,
      server: {
        name: info?.name ?? null,
        version: info?.version ?? null,
      },
      tools: tools.tools.map((t) => t.name),
      error: null,
    };
  } catch (err) {
    const classified = classifyError(err);
    if (
      classified.code === "unreachable" ||
      classified.code === "timeout" ||
      classified.code === "backend"
    ) {
      resetClient();
    }
    return {
      connected: false,
      configured: true,
      mode,
      url,
      server: null,
      tools: [],
      error: { code: classified.code, message: classified.message },
    };
  }
}
