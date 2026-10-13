"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MarkdownView } from "@/components/markdown";
import { ErrorCard, LoadingBlocks } from "@/components/data-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, ApiRequestError } from "@/lib/api";
import type { IndexPayload, WikiListPayload } from "@/lib/types";
import { cn } from "cn";

type WikisState =
  | { kind: "loading" }
  | { kind: "ready"; data: WikiListPayload }
  | { kind: "error"; message: string };

type IndexState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; data: IndexPayload }
  | { kind: "error"; message: string };

export function WikiBrowser({ initialWiki }: { initialWiki: string }) {
  const router = useRouter();
  const [wikis, setWikis] = useState<WikisState>({ kind: "loading" });
  const [selected, setSelected] = useState(initialWiki);
  const [index, setIndex] = useState<IndexState>({ kind: "loading" });
  const [nonce, setNonce] = useState(0);

  function retry() {
    setWikis({ kind: "loading" });
    setIndex({ kind: "loading" });
    setNonce((n) => n + 1);
  }

  useEffect(() => {
    let active = true;
    void apiGet<WikiListPayload>("/api/wikis").then(
      (data) => {
        if (!active) return;
        setWikis({ kind: "ready", data });
        const names = data.wikis.map((w) => w.name);
        if (!names.includes(initialWiki)) {
          const preferred = data.default ?? "";
          const fallback = names.includes(preferred)
            ? preferred
            : (data.wikis.find((w) => w.status === "active")?.name ?? "");
          setSelected(fallback);
          router.replace(`/wikis?wiki=${encodeURIComponent(fallback)}`);
        }
      },
      (err: unknown) => {
        if (!active) return;
        setWikis({
          kind: "error",
          message:
            err instanceof ApiRequestError ? err.message : "Could not load wikis.",
        });
      },
    );
    return () => {
      active = false;
    };
  }, [initialWiki, nonce, router]);

  useEffect(() => {
    if (wikis.kind !== "ready") return;
    if (
      wikis.data.wikis.length > 0 &&
      !wikis.data.wikis.some((w) => w.name === selected)
    ) {
      return;
    }
    let active = true;
    void apiGet<IndexPayload>(
      `/api/index?wiki=${encodeURIComponent(selected)}`,
    ).then(
      (data) => {
        if (active) setIndex({ kind: "ready", data });
      },
      (err: unknown) => {
        if (!active) return;
        setIndex({
          kind: "error",
          message:
            err instanceof ApiRequestError ? err.message : "Could not load index.",
        });
      },
    );
    return () => {
      active = false;
    };
  }, [selected, wikis]);

  function pick(name: string) {
    setSelected(name);
    setIndex({ kind: "loading" });
    router.replace(`/wikis?wiki=${encodeURIComponent(name)}`);
  }

  if (wikis.kind === "loading") return <LoadingBlocks rows={4} />;
  if (wikis.kind === "error") {
    return (
      <ErrorCard
        title="Wikis unavailable"
        message={wikis.message}
        onRetry={retry}
      />
    );
  }

  const active = wikis.data.wikis.filter((w) => w.status === "active");
  const selectedEntry = wikis.data.wikis.find((w) => w.name === selected);
  const baseDir =
    selectedEntry &&
    !selectedEntry.is_hub &&
    selectedEntry.path &&
    selectedEntry.path !== "<HUB>"
      ? selectedEntry.path
      : "";

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="text-caption">Registered wikis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {active.map((w) => (
            <button
              key={w.name}
              type="button"
              onClick={() => pick(w.name)}
              aria-pressed={selected === w.name}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-caption transition-colors",
                selected === w.name
                  ? "border-primary/60 bg-accent text-foreground"
                  : "border-border text-muted-foreground hover:border-input hover:text-foreground",
              )}
            >
              <span className="truncate">{w.name}</span>
              {w.is_hub && <Badge variant="outline">hub</Badge>}
            </button>
          ))}
          <p className="pt-1 text-meta text-muted-foreground">
            {active.length} active of {wikis.data.count} registered
            {wikis.data.truncated ? " (list truncated)" : ""}
          </p>
        </CardContent>
      </Card>

      <div className="min-w-0">
        {index.kind === "idle" && (
          <Card>
            <CardContent className="py-8 text-center text-caption text-muted-foreground">
              Select a wiki to view its index.
            </CardContent>
          </Card>
        )}
        {index.kind === "loading" && <Skeleton className="h-64 w-full" />}
        {index.kind === "error" && (
          <ErrorCard
            title="Index unavailable"
            message={index.message}
            onRetry={retry}
          />
        )}
        {index.kind === "ready" && (
          <Card>
            <CardHeader>
              <CardTitle className="font-mono text-caption">
                {index.data.wiki === "" ? "hub index" : `${index.data.wiki} index`}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <MarkdownView markdown={index.data.markdown} baseDir={baseDir} />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
