import { connection } from "next/server";
import { NextResponse } from "next/server";
import { probeBackend } from "@/lib/mcp-client";
import { handleApi } from "@/lib/api-helpers";

export async function GET(): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const status = await probeBackend();
    return NextResponse.json(status);
  });
}
