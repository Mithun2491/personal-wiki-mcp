"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search as SearchIcon } from "lucide-react";
import { ErrorCard, LoadingBlocks } from "@/components/data-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiGet, ApiRequestError } from "@/lib/api";
import type { SearchPayload, WikiListPayload } from "@/lib/types";

type ResultState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; data: SearchPayload }
  | { kind: "error"; message: string };

export function SearchView({
  initialQuery,
  initialWiki,
}: {
  initialQuery: string;
  initialWiki: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [wiki, setWiki] = useState(initialWiki);
  const [wikis, setWikis] = useState<WikiListPayload | null>(null);
  const [result, setResult] = useState<ResultState>(
    initialQuery ? { kind: "loading" } : { kind: "idle" },
  );
  const [nonce, setNonce] = useState(0);

  function retry() {
    setResult(initialQuery ? { kind: "loading" } : { kind: "idle" });
    setNonce((n) => n + 1);
  }

  useEffect(() => {
    let active = true;
    void apiGet<WikiListPayload>("/api/wikis").then(
      (data) => {
        if (active) setWikis(data);
      },
      () => {
        if (active) setWikis(null);
      },
    );
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!initialQuery) return;
    let active = true;
    const url =
      `/api/search?query=${encodeURIComponent(initialQuery)}` +
      `&wiki=${encodeURIComponent(initialWiki)}&maxResults=20`;
    void apiGet<SearchPayload>(url).then(
      (data) => {
        if (active) setResult({ kind: "ready", data });
      },
      (err: unknown) => {
        if (!active) return;
        setResult({
          kind: "error",
          message:
            err instanceof ApiRequestError ? err.message : "Search failed.",
        });
      },
    );
    return () => {
      active = false;
    };
  }, [initialQuery, initialWiki, nonce]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    router.push(
      `/search?query=${encodeURIComponent(query.trim())}&wiki=${encodeURIComponent(wiki)}`,
    );
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-1.5">
          <Label htmlFor="search-query">Query</Label>
          <Input
            id="search-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search wikis…"
            maxLength={200}
            autoComplete="off"
          />
        </div>
        <div className="space-y-1.5 sm:w-48">
          <Label htmlFor="search-wiki">Wiki</Label>
          <select
            id="search-wiki"
            value={wiki}
            onChange={(e) => setWiki(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-card px-2.5 text-caption text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <option value="">All wikis</option>
            {wikis?.wikis
              .filter((w) => w.status === "active")
              .map((w) => (
                <option key={w.name} value={w.name}>
                  {w.name}
                </option>
              ))}
          </select>
        </div>
        <Button type="submit" className="sm:w-auto">
          <SearchIcon aria-hidden className="size-4" /> Search
        </Button>
      </form>

      {result.kind === "idle" && (
        <Card>
          <CardContent className="py-8 text-center text-caption text-muted-foreground">
            Enter a query to search across wiki articles.
          </CardContent>
        </Card>
      )}
      {result.kind === "loading" && <LoadingBlocks rows={4} />}
      {result.kind === "error" && (
        <ErrorCard
          title="Search failed"
          message={result.message}
          onRetry={retry}
        />
      )}
      {result.kind === "ready" && (
        <div className="space-y-3">
          <p className="text-caption text-muted-foreground">
            {result.data.match_count} match{result.data.match_count === 1 ? "" : "es"} in{" "}
            {result.data.files_scanned} file{result.data.files_scanned === 1 ? "" : "s"}
            {result.data.wiki ? ` · ${result.data.wiki}` : " · all wikis"}
            {result.data.truncated ? " · results truncated" : ""}
          </p>
          {result.data.matches.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-caption text-muted-foreground">
                No matches. Try different terms or another wiki.
              </CardContent>
            </Card>
          ) : (
            result.data.matches.map((m, i) => (
              <Card key={`${m.path}:${m.line}:${i}`}>
                <CardContent className="space-y-1.5 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/article?path=${encodeURIComponent(m.path)}`}
                      className="min-w-0 truncate font-mono text-caption text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
                    >
                      {m.path}
                    </Link>
                    <Badge variant="outline">line {m.line}</Badge>
                  </div>
                  <p className="text-caption whitespace-pre-wrap text-muted-foreground">
                    {m.snippet}
                  </p>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}
