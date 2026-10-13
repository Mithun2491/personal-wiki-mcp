import { connection } from "next/server";
import { NextRequest, NextResponse } from "next/server";
import { callWikiTool } from "@/lib/mcp-client";
import { handleApi } from "@/lib/api-helpers";
import {
  searchQuerySchema,
  wikiNameSchema,
  maxResultsSchema,
  searchResultSchema,
} from "@/lib/validation";

export async function GET(request: NextRequest): Promise<NextResponse> {
  await connection();
  return handleApi(async () => {
    const params = request.nextUrl.searchParams;
    const query = searchQuerySchema.parse(params.get("query") ?? "");
    const wiki = wikiNameSchema.parse(params.get("wiki") ?? "");
    const maxResults = maxResultsSchema.parse(
      params.get("maxResults") ?? undefined,
    );
    const text = await callWikiTool("search_wiki", {
      query,
      wiki,
      max_results: maxResults,
    });
    const data = searchResultSchema.parse(JSON.parse(text));
    return NextResponse.json(data);
  }, "search");
}
