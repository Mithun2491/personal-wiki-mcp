import { afterEach, describe, expect, it, vi } from "vitest";
import { StreamableHTTPError } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { UnauthorizedError } from "@modelcontextprotocol/sdk/client/auth.js";
import { McpError, fingerprintError } from "@/lib/mcp-client";
import { errorResponse, handleApi, jsonError, logProbeFailure } from "@/lib/api-helpers";
import { articlePathSchema } from "@/lib/validation";

afterEach(() => {
  vi.restoreAllMocks();
});

function loggedJson(spy: ReturnType<typeof vi.spyOn>): Record<string, unknown>[] {
  return spy.mock.calls.map((args) => JSON.parse(String(args[0])));
}

describe("fingerprintError", () => {
  it("maps an HTTP 401 transport failure to unauthorized with its status", () => {
    const err = new StreamableHTTPError(401, "Unauthorized");
    expect(fingerprintError(err)).toEqual({
      name: "StreamableHTTPError",
      code: "unauthorized",
      httpStatus: 401,
    });
  });

  it("maps an HTTP 5xx transport failure to backend with its status", () => {
    const err = new StreamableHTTPError(503, "Service Unavailable");
    expect(fingerprintError(err)).toEqual({
      name: "StreamableHTTPError",
      code: "backend",
      httpStatus: 503,
    });
  });

  it("maps an HTTP 404 transport failure to unreachable with its status", () => {
    const err = new StreamableHTTPError(404, "Not Found");
    expect(fingerprintError(err)).toEqual({
      name: "StreamableHTTPError",
      code: "unreachable",
      httpStatus: 404,
    });
  });

  it("maps a bare UnauthorizedError to unauthorized without a status", () => {
    expect(fingerprintError(new UnauthorizedError())).toEqual({
      name: "UnauthorizedError",
      code: "unauthorized",
      httpStatus: null,
    });
  });

  it("maps a refused connection to unreachable without a status", () => {
    const err = new TypeError("fetch failed") as TypeError & { code?: string };
    err.cause = { code: "ECONNREFUSED" };
    expect(fingerprintError(err)).toEqual({
      name: "TypeError",
      code: "unreachable",
      httpStatus: null,
    });
  });

  it("maps an abort to timeout", () => {
    const err = new Error("aborted");
    err.name = "AbortError";
    expect(fingerprintError(err)).toEqual({
      name: "AbortError",
      code: "timeout",
      httpStatus: null,
    });
  });

  it("maps an unknown exception to backend without a status", () => {
    expect(fingerprintError(new Error("weird protocol state"))).toEqual({
      name: "Error",
      code: "backend",
      httpStatus: null,
    });
  });

  it("preserves the code of an existing McpError", () => {
    expect(fingerprintError(new McpError("timeout", "slow"))).toEqual({
      name: "McpError",
      code: "timeout",
      httpStatus: null,
    });
  });
});

describe("public error responses are unchanged", () => {
  it("keeps the {error:{code,message}} shape with mapped statuses", async () => {
    const res = jsonError("not_found", "gone");
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: { code: "not_found", message: "gone" } });
  });

  it("still maps backend tool text to 404/400/502", async () => {
    expect(errorResponse(new McpError("backend", "unknown wiki: nope")).status).toBe(404);
    expect(errorResponse(new McpError("backend", "path escapes the wiki root")).status).toBe(400);
    expect(errorResponse(new McpError("backend", "something odd")).status).toBe(502);
    expect(errorResponse(new McpError("unauthorized", "nope")).status).toBe(502);
  });

  it("still maps invalid input to 400", async () => {
    const res = await handleApi(async () => {
      articlePathSchema.parse("../server.py");
      throw new Error("unreachable");
    });
    expect(res.status).toBe(400);
  });
});

describe("diagnostic logging", () => {
  it("logs one JSON line per 5xx with route, id, class, code, and status", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const res = await handleApi(async () => {
      throw new StreamableHTTPError(500, "boom");
    }, "wikis");
    expect(res.status).toBe(500);
    expect(spy).toHaveBeenCalledTimes(1);
    const [line] = loggedJson(spy);
    expect(line.route).toBe("wikis");
    expect(line.correlationId).toMatch(/^[0-9a-f-]{8,36}$/);
    expect(line.error).toBe("StreamableHTTPError");
    expect(line.code).toBe("backend");
    expect(line.httpStatus).toBe(500);
    expect(Object.keys(line).sort()).toEqual(
      ["code", "correlationId", "error", "httpStatus", "route"].sort(),
    );
  });

  it("never logs raw messages, tokens, or headers", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    await handleApi(async () => {
      throw new McpError(
        "backend",
        "note Bearer FAKE-SECRET-123 and Authorization: Bearer FAKE-SECRET-123",
      );
    }, "search");
    expect(spy).toHaveBeenCalledTimes(1);
    const serialized = String(spy.mock.calls[0][0]);
    expect(serialized).not.toContain("FAKE-SECRET-123");
    expect(serialized).not.toContain("Bearer");
    expect(serialized).not.toContain("Authorization");
  });

  it("does not log 4xx validation failures", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const res = await handleApi(async () => {
      articlePathSchema.parse("../server.py");
      throw new Error("unreachable");
    });
    expect(res.status).toBe(400);
    expect(spy).not.toHaveBeenCalled();
  });

  it("logs probe failures with the probe marker and classification", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    logProbeFailure("status", "backend");
    expect(spy).toHaveBeenCalledTimes(1);
    const [line] = loggedJson(spy);
    expect(line).toMatchObject({ route: "status", error: "probe", code: "backend", httpStatus: null });
  });

  it("a throwing logger cannot change the API response", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {
      throw new Error("logger exploded");
    });
    const res = await handleApi(async () => {
      throw new StreamableHTTPError(503, "down");
    }, "index");
    expect(res.status).toBe(500);
    expect(await res.json()).toEqual({
      error: { code: "internal", message: "Something went wrong on the server." },
    });
    spy.mockRestore();
  });
});
