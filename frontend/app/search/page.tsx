import { PageContainer } from "@/components/page-container";
import { SearchView } from "./search-view";

export const instant = false;

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function SearchPage({ searchParams }: PageProps<"/search">) {
  const params = await searchParams;
  const query = firstParam(params.query);
  const wiki = firstParam(params.wiki);
  return (
    <PageContainer title="Search" description="Full-text search across wiki articles.">
      <SearchView
        key={`${query}:${wiki}`}
        initialQuery={query}
        initialWiki={wiki}
      />
    </PageContainer>
  );
}
