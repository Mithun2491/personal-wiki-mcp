import type { ApiErrorBody, ApiErrorCode } from "@/lib/types";

export class ApiRequestError extends Error {
  status: number;
  code: ApiErrorCode;

  constructor(status: number, code: ApiErrorCode, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { cache: "no-store" });
  } catch {
    throw new ApiRequestError(0, "unreachable", "Could not reach the app server.");
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = (body as ApiErrorBody | null)?.error;
    throw new ApiRequestError(
      res.status,
      err?.code ?? "internal",
      err?.message ?? "Request failed.",
    );
  }
  return body as T;
}
