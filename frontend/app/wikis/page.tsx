import { PageContainer } from "@/components/page-container";
import { WikiBrowser } from "./wiki-browser";

export const instant = false;

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function WikisPage({ searchParams }: PageProps<"/wikis">) {
  const params = await searchParams;
  const initialWiki = firstParam(params.wiki);
  return (
    <PageContainer
      title="Wikis"
      description="Browse registered wikis and their index structure."
    >
      <WikiBrowser key={initialWiki} initialWiki={initialWiki} />
    </PageContainer>
  );
}
