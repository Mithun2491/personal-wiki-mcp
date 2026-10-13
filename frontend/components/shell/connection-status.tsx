"use client";

import { useCallback, useEffect, useState } from "react";
import { cn } from "cn";
import { Button } from "@/components/ui/button";

type StatusState =
  | { kind: "checking" }
  | { kind: "connected"; mode: "local" | "remote" }
  | { kind: "error"; message: string };

const LABEL: Record<StatusState["kind"], string> = {
  checking: "Checking…",
  connected: "Connected",
  error: "Disconnected",
};

function dotClass(kind: StatusState["kind"]) {
  return cn(
    "size-1.5 shrink-0 rounded-full",
    kind === "checking" && "bg-muted-foreground animate-pulse",
    kind === "connected" && "bg-success",
    kind === "error" && "bg-destructive",
  );
}

async function fetchStatus(): Promise<StatusState> {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) {
      return { kind: "error", message: "Backend unreachable" };
    }
    const data: { connected: boolean; mode?: "local" | "remote" } =
      await res.json();
    if (data.connected && (data.mode === "local" || data.mode === "remote")) {
      return { kind: "connected", mode: data.mode };
    }
    return { kind: "error", message: "Backend unreachable" };
  } catch {
    return { kind: "error", message: "Backend unreachable" };
  }
}

export function ConnectionStatus() {
  const [state, setState] = useState<StatusState>({ kind: "checking" });

  const refresh = useCallback(async () => {
    const result = await fetchStatus();
    setState(result);
  }, []);

  useEffect(() => {
    let active = true;
    void fetchStatus().then((result) => {
      if (active) setState(result);
    });
    return () => {
      active = false;
    };
  }, []);

  const title =
    state.kind === "connected"
      ? `MCP ${state.mode === "remote" ? "remote" : "local"} service connected`
      : state.kind === "error"
        ? state.message
        : "Checking MCP connection";

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => void refresh()}
      aria-label={`MCP connection: ${LABEL[state.kind]}. Refresh status.`}
      title={title}
      className="gap-1.5 text-caption text-muted-foreground"
    >
      <span aria-hidden className={dotClass(state.kind)} />
      <span className="hidden sm:inline">{LABEL[state.kind]}</span>
    </Button>
  );
}
