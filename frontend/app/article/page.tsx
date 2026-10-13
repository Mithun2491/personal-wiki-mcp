import { PageContainer } from "@/components/page-container";
import { ArticleReader } from "./article-reader";

export const instant = false;

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export default async function ArticlePage({
  searchParams,
}: PageProps<"/article">) {
  const params = await searchParams;
  const path = firstParam(params.path);
  return (
    <PageContainer title="Reader" description="Read a wiki article.">
      <ArticleReader key={path} initialPath={path} />
    </PageContainer>
  );
}
