import { connection } from "next/server";
import { NextResponse } from "next/server";
import { probeBackend } from "@/lib/mcp-client";
import { handleApi, logProbeFailure } from "@/lib/api-helpers";

export async function GET(): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const status = await probeBackend();
    if (!status.connected && status.error) {
      logProbeFailure("status", status.error.code);
    }
    return NextResponse.json(status);
  }, "status");
}
