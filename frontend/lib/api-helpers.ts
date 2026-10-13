import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { McpError, fingerprintError, type ErrorFingerprint } from "@/lib/mcp-client";
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

export interface DiagnosticLog {
  route: string;
  correlationId: string;
  error: string;
  code: ApiErrorCode;
  httpStatus: number | null;
}

function emitDiagnostic(log: DiagnosticLog): void {
  try {
    console.error(JSON.stringify(log));
  } catch {
    /* logging must never throw */
  }
}

function safeFingerprint(err: unknown): ErrorFingerprint {
  try {
    return fingerprintError(err);
  } catch {
    return { name: "unknown", code: "internal", httpStatus: null };
  }
}

export function logProbeFailure(route: string, code: ApiErrorCode): void {
  emitDiagnostic({
    route,
    correlationId: randomUUID().slice(0, 8),
    error: "probe",
    code,
    httpStatus: null,
  });
}

export async function handleApi(
  fn: () => Promise<NextResponse>,
  route = "api",
): Promise<NextResponse> {
  try {
    return await fn();
  } catch (err) {
    const res =
      err instanceof Error &&
      (err.name === "TimeoutError" || err.name === "AbortError")
        ? jsonError("timeout", "The wiki backend did not respond in time.")
        : errorResponse(err);
    if (res.status >= 500) {
      const fp = safeFingerprint(err);
      emitDiagnostic({
        route,
        correlationId: randomUUID().slice(0, 8),
        error: fp.name,
        code: fp.code,
        httpStatus: fp.httpStatus,
      });
    }
    return res;
  }
}
