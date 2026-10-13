import { connection } from "next/server";
import { NextRequest, NextResponse } from "next/server";
import { callWikiTool } from "@/lib/mcp-client";
import { handleApi } from "@/lib/api-helpers";
import { articlePathSchema } from "@/lib/validation";
import type { ArticlePayload } from "@/lib/types";

export async function GET(request: NextRequest): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const raw = request.nextUrl.searchParams.get("path") ?? "";
    const path = articlePathSchema.parse(raw);
    const markdown = await callWikiTool("read_article", { path });
    const payload: ArticlePayload = { path, markdown };
    return NextResponse.json(payload);
  }, "article");
}
