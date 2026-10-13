import { connection } from "next/server";
import { NextRequest, NextResponse } from "next/server";
import { callWikiTool } from "@/lib/mcp-client";
import { handleApi } from "@/lib/api-helpers";
import { wikiNameSchema } from "@/lib/validation";
import type { IndexPayload } from "@/lib/types";

export async function GET(request: NextRequest): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const raw = request.nextUrl.searchParams.get("wiki") ?? "";
    const wiki = wikiNameSchema.parse(raw);
    const markdown = await callWikiTool("get_wiki_index", { wiki });
    const payload: IndexPayload = { wiki, markdown };
    return NextResponse.json(payload);
  }, "index");
}
