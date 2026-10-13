"use client";

import { useSyncExternalStore } from "react";
import { Menu, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConnectionStatus } from "@/components/shell/connection-status";

const IS_MAC =
  typeof navigator !== "undefined" &&
  /mac|iphone|ipad/i.test(navigator.userAgent);

function subscribeIsMac() {
  return () => {};
}

function getIsMacSnapshot() {
  return IS_MAC;
}

function getIsMacServerSnapshot() {
  return false;
}

export function Header({
  onOpenMobileNav,
  onOpenSearch,
}: {
  onOpenMobileNav: () => void;
  onOpenSearch?: () => void;
}) {
  const mac = useSyncExternalStore(
    subscribeIsMac,
    getIsMacSnapshot,
    getIsMacServerSnapshot,
  );

  return (
    <header className="sticky top-0 z-30 flex h-(--header-height) shrink-0 items-center gap-2 border-b border-border bg-background/95 px-3 backdrop-blur-xs sm:px-4">
      <Button
        variant="ghost"
        size="icon-sm"
        className="lg:hidden"
        onClick={onOpenMobileNav}
        aria-label="Open navigation"
      >
        <Menu aria-hidden className="size-4" />
      </Button>

      <button
        type="button"
        onClick={onOpenSearch}
        className="group flex h-8 min-w-0 max-w-md flex-1 items-center gap-2 rounded-md border border-border bg-card/60 px-2.5 text-caption text-muted-foreground transition-colors hover:border-input hover:bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        aria-label="Search wikis"
      >
        <Search aria-hidden className="size-3.5 shrink-0" />
        <span className="truncate">Search wikis…</span>
        <span
          aria-hidden
          className="ml-auto hidden font-mono text-meta text-muted-foreground/70 sm:inline"
        >
          {mac ? "⌘K" : "Ctrl K"}
        </span>
      </button>

      <div className="ml-auto flex items-center gap-2">
        <ConnectionStatus />
      </div>
    </header>
  );
}
