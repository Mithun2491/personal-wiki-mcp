import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { McpError } from "@/lib/mcp-client";
import type { ApiErrorCode } from "@/lib/types";

const STATUS_FOR_CODE: Record<ApiErrorCode, number> = {
  invalid_request: 400,
  not_found: 404,
  unauthorized: 502,
  config: 503,
  unreachable: 502,
  timeout: 504,
  backend: 502,
  internal: 500,
};

export function jsonError(code: ApiErrorCode, message: string): NextResponse {
  return NextResponse.json(
    { error: { code, message } },
    { status: STATUS_FOR_CODE[code] },
  );
}

function mapToolMessage(message: string): { code: ApiErrorCode; message: string } {
  const m = message.toLowerCase();
  if (
    m.includes("unknown wiki") ||
    m.includes("file not found") ||
    m.includes("index not found")
  ) {
    return { code: "not_found", message };
  }
  if (
    m.includes("path escapes") ||
    m.includes("only markdown") ||
    m.includes("path must") ||
    m.includes("path is a directory") ||
    m.includes("null byte") ||
    m.includes("query must") ||
    m.includes("path could not")
  ) {
    return { code: "invalid_request", message };
  }
  return { code: "backend", message };
}

export function errorResponse(err: unknown): NextResponse {
  if (err instanceof McpError) {
    if (err.code === "backend") {
      const mapped = mapToolMessage(err.message);
      return jsonError(mapped.code, mapped.message);
    }
    return jsonError(err.code, err.message);
  }
  if (err instanceof ZodError) {
    const first = err.issues[0];
    return jsonError(
      "invalid_request",
      first ? first.message : "Invalid request.",
    );
  }
  return jsonError("internal", "Something went wrong on the server.");
}

export async function handleApi(
  fn: () => Promise<NextResponse>,
): Promise<NextResponse> {
  try {
    return await fn();
  } catch (err) {
    if (
      err instanceof Error &&
      (err.name === "TimeoutError" || err.name === "AbortError")
    ) {
      return jsonError("timeout", "The wiki backend did not respond in time.");
    }
    return errorResponse(err);
  }
}
