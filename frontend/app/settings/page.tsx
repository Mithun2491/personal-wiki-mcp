"use client";

import { useEffect, useState } from "react";
import { PageContainer } from "@/components/page-container";
import { ErrorCard, LoadingBlocks } from "@/components/data-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiGet, ApiRequestError } from "@/lib/api";
import type { StatusPayload } from "@/lib/types";
import { cn } from "cn";

type View =
  | { kind: "loading" }
  | { kind: "ready"; status: StatusPayload }
  | { kind: "error"; message: string };

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 py-2">
      <span className="text-caption text-muted-foreground">{label}</span>
      <span className="min-w-0 text-right text-caption text-foreground">{children}</span>
    </div>
  );
}

export default function SettingsPage() {
  const [view, setView] = useState<View>({ kind: "loading" });
  const [nonce, setNonce] = useState(0);

  function retry() {
    setView({ kind: "loading" });
    setNonce((n) => n + 1);
  }

  useEffect(() => {
    let active = true;
    void apiGet<StatusPayload>("/api/status").then(
      (status) => {
        if (active) setView({ kind: "ready", status });
      },
      (err: unknown) => {
        if (!active) return;
        setView({
          kind: "error",
          message:
            err instanceof ApiRequestError ? err.message : "Could not load settings.",
        });
      },
    );
    return () => {
      active = false;
    };
  }, [nonce]);

  return (
    <PageContainer
      title="Settings"
      description="Connection status and backend details."
      actions={
        <Button variant="outline" size="sm" onClick={retry}>
          Refresh
        </Button>
      }
    >
      {view.kind === "loading" && <LoadingBlocks rows={2} />}
      {view.kind === "error" && (
        <ErrorCard
          title="Settings unavailable"
          message={view.message}
          onRetry={retry}
        />
      )}
      {view.kind === "ready" && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Backend</CardTitle>
              <CardDescription>Where the hub reads from</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row label="Status">
                <span className="inline-flex items-center gap-2">
                  <span
                    aria-hidden
                    className={cn(
                      "size-2 rounded-full",
                      view.status.connected ? "bg-success" : "bg-destructive",
                    )}
                  />
                  {view.status.connected ? "Connected" : "Disconnected"}
                </span>
              </Row>
              <Row label="Mode">
                {view.status.mode ? (
                  <Badge variant="secondary">{view.status.mode}</Badge>
                ) : (
                  <span className="text-muted-foreground">unknown</span>
                )}
              </Row>
              <Row label="Backend URL">
                <span className="block max-w-full truncate font-mono text-meta">
                  {view.status.url ?? "not configured"}
                </span>
              </Row>
              <Row label="Server">
                {view.status.server?.name
                  ? `${view.status.server.name}${view.status.server.version ? ` ${view.status.server.version}` : ""}`
                  : "unknown"}
              </Row>
              {view.status.error && (
                <p className="py-2 text-caption text-warning">
                  {view.status.error.message}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Credentials</CardTitle>
              <CardDescription>Token handling</CardDescription>
            </CardHeader>
            <CardContent className="divide-y divide-border">
              <Row label="Token configured">
                {view.status.configured ? (
                  <Badge variant="secondary">yes</Badge>
                ) : (
                  <Badge variant="destructive">no</Badge>
                )}
              </Row>
              <p className="py-2 text-caption text-muted-foreground">
                The token lives only in server-side environment variables and is
                never sent to the browser.
              </p>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Tools</CardTitle>
              <CardDescription>Live catalog from the backend handshake</CardDescription>
            </CardHeader>
            <CardContent>
              {view.status.tools.length === 0 ? (
                <p className="text-caption text-muted-foreground">
                  No tools reported. Check the connection above.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {view.status.tools.map((t) => (
                    <Badge key={t} variant="secondary" className="font-mono">
                      {t}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
