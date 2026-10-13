"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Library, Search, Wrench } from "lucide-react";
import { PageContainer } from "@/components/page-container";
import { ErrorCard, LoadingBlocks } from "@/components/data-state";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiGet, ApiRequestError } from "@/lib/api";
import type { StatusPayload, WikiListPayload } from "@/lib/types";
import { cn } from "cn";

type View =
  | { kind: "loading" }
  | { kind: "ready"; status: StatusPayload; wikis: WikiListPayload | null }
  | { kind: "error"; message: string };

function ConnectionDot({ connected }: { connected: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "size-2 shrink-0 rounded-full",
        connected ? "bg-success" : "bg-destructive",
      )}
    />
  );
}

export default function OverviewPage() {
  const [view, setView] = useState<View>({ kind: "loading" });
  const [nonce, setNonce] = useState(0);

  function retry() {
    setView({ kind: "loading" });
    setNonce((n) => n + 1);
  }

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiGet<StatusPayload>("/api/status"),
      apiGet<WikiListPayload>("/api/wikis").catch(() => null),
    ]).then(([status, wikis]) => {
      if (!active) return;
      setView({ kind: "ready", status, wikis });
    }).catch((err: unknown) => {
      if (!active) return;
      setView({
        kind: "error",
        message:
          err instanceof ApiRequestError
            ? err.message
            : "Could not load overview.",
      });
    });
    return () => {
      active = false;
    };
  }, [nonce]);

  return (
    <PageContainer
      title="Overview"
      description="Connection, wikis, and tools — all live from the MCP backend."
      actions={
        view.kind === "ready" && (
          <Link
            href="/search"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            Search wikis
          </Link>
        )
      }
    >
      {view.kind === "loading" && <LoadingBlocks rows={3} />}
      {view.kind === "error" && (
        <ErrorCard
          title="Overview unavailable"
          message={view.message}
          onRetry={retry}
        />
      )}
      {view.kind === "ready" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Connection</CardTitle>
              <CardDescription>MCP backend handshake</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-caption">
              <p className="flex items-center gap-2 text-body text-foreground">
                <ConnectionDot connected={view.status.connected} />
                {view.status.connected ? "Connected" : "Disconnected"}
                {view.status.mode && (
                  <Badge variant="secondary">{view.status.mode}</Badge>
                )}
              </p>
              {view.status.server && (
                <p className="text-muted-foreground">
                  {view.status.server.name ?? "unknown server"}
                  {view.status.server.version && ` ${view.status.server.version}`}
                </p>
              )}
              {view.status.url && (
                <p className="truncate font-mono text-meta text-muted-foreground">
                  {view.status.url}
                </p>
              )}
              {view.status.error && (
                <p className="text-warning">{view.status.error.message}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Library aria-hidden className="size-4" /> Wikis
              </CardTitle>
              <CardDescription>Active wikis from the registry</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {view.wikis == null ? (
                <Skeleton className="h-10 w-full" />
              ) : (
                <>
                  {view.wikis.wikis
                    .filter((w) => w.status === "active")
                    .map((w) => (
                      <Link
                        key={w.name}
                        href={`/wikis?wiki=${encodeURIComponent(w.name)}`}
                        className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-caption transition-colors hover:border-input hover:bg-card"
                      >
                        <span className="truncate text-foreground">
                          {w.name}
                          {w.is_hub && (
                            <Badge variant="outline" className="ml-2">
                              hub
                            </Badge>
                          )}
                        </span>
                        <span className="shrink-0 text-meta text-muted-foreground">
                          {w.description ?? "no description"}
                        </span>
                      </Link>
                    ))}
                  <p className="text-meta text-muted-foreground">
                    {view.wikis.wikis.filter((w) => w.status === "active").length}{" "}
                    active of {view.wikis.count} registered
                    {view.wikis.truncated ? " (list truncated)" : ""}
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wrench aria-hidden className="size-4" /> Tools
              </CardTitle>
              <CardDescription>Read-only tools exposed by the backend</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {view.status.tools.map((t) => (
                  <Badge key={t} variant="secondary" className="font-mono">
                    {t}
                  </Badge>
                ))}
              </div>
              <Link
                href="/search"
                className={buttonVariants({ variant: "ghost", size: "sm" })}
              >
                <Search aria-hidden className="size-3.5" /> Try search
              </Link>
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
