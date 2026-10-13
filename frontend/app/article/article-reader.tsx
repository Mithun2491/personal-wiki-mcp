"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MarkdownView } from "@/components/markdown";
import { ErrorCard, LoadingBlocks } from "@/components/data-state";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, ApiRequestError } from "@/lib/api";
import type { ArticlePayload } from "@/lib/types";

type View =
  | { kind: "empty" }
  | { kind: "loading" }
  | { kind: "ready"; data: ArticlePayload }
  | { kind: "stale" }
  | { kind: "error"; message: string };

function baseDirOf(path: string): string {
  const i = path.lastIndexOf("/");
  return i <= 0 ? "" : path.slice(0, i);
}

export function ArticleReader({ initialPath }: { initialPath: string }) {
  const [view, setView] = useState<View>(
    initialPath ? { kind: "loading" } : { kind: "empty" },
  );
  const [nonce, setNonce] = useState(0);

  function retry() {
    setView(initialPath ? { kind: "loading" } : { kind: "empty" });
    setNonce((n) => n + 1);
  }

  useEffect(() => {
    if (!initialPath) return;
    let active = true;
    void apiGet<ArticlePayload>(
      `/api/article?path=${encodeURIComponent(initialPath)}`,
    ).then(
      (data) => {
        if (active) setView({ kind: "ready", data });
      },
      (err: unknown) => {
        if (!active) return;
        if (err instanceof ApiRequestError && err.code === "not_found") {
          setView({ kind: "stale" });
        } else {
          setView({
            kind: "error",
            message:
              err instanceof ApiRequestError ? err.message : "Could not load article.",
          });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [initialPath, nonce]);

  if (view.kind === "empty") {
    return (
      <Card>
        <CardContent className="space-y-3 py-8 text-center">
          <p className="text-caption text-muted-foreground">
            No article selected. Browse a wiki or run a search to pick one.
          </p>
          <div className="flex justify-center gap-2">
            <Link
              href="/wikis"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Browse wikis
            </Link>
            <Link
              href="/search"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Search
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (view.kind === "loading") {
    return (
      <div className="mx-auto w-full max-w-(--reading-max) space-y-3">
        <Skeleton className="h-5 w-2/3" />
        <LoadingBlocks rows={4} />
      </div>
    );
  }

  if (view.kind === "stale") {
    return (
      <ErrorCard
        title="Article not found"
        message="This link looks stale — the article may have moved or been removed. Pick a fresh path below."
        onRetry={retry}
      >
        <Link
          href="/wikis"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Browse wikis
        </Link>
        <Link
          href="/search"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Search
        </Link>
      </ErrorCard>
    );
  }

  if (view.kind === "error") {
    return (
      <ErrorCard
        title="Article unavailable"
        message={view.message}
        onRetry={retry}
      />
    );
  }

  return (
    <Card className="mx-auto w-full max-w-(--reading-max)">
      <CardHeader>
        <CardTitle className="truncate font-mono text-caption text-muted-foreground">
          {view.data.path}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <MarkdownView markdown={view.data.markdown} baseDir={baseDirOf(view.data.path)} />
      </CardContent>
    </Card>
  );
}
