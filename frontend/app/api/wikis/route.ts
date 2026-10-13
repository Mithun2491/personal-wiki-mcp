import { connection } from "next/server";
import { NextResponse } from "next/server";
import { callWikiTool } from "@/lib/mcp-client";
import { handleApi } from "@/lib/api-helpers";
import { wikiListSchema } from "@/lib/validation";

export async function GET(): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const text = await callWikiTool("list_wikis", {});
    const data = wikiListSchema.parse(JSON.parse(text));
    return NextResponse.json(data);
  }, "wikis");
}
