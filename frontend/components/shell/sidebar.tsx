"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen, Library } from "lucide-react";
import { cn } from "cn";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { NAV_ITEMS } from "@/components/shell/nav-items";

function NavList({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5 px-2">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        const link = (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-8 items-center gap-2.5 rounded-md px-2 text-caption font-medium transition-colors",
              "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
            )}
          >
            <Icon
              aria-hidden
              className={cn(
                "size-4 shrink-0",
                active ? "text-primary" : "opacity-70",
              )}
            />
            {!collapsed && <span className="truncate">{label}</span>}
          </Link>
        );

        if (collapsed) {
          return (
            <Tooltip key={href}>
              <TooltipTrigger delay={0} render={<div />}>{link}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          );
        }
        return link;
      })}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="flex h-10 items-center gap-2.5 px-4">
      <Library aria-hidden className="size-4 shrink-0 text-primary" />
      {!collapsed && (
        <span className="truncate text-caption font-semibold tracking-tight text-sidebar-foreground">
          Knowledge Hub
        </span>
      )}
    </div>
  );
}

export function Sidebar({
  collapsed,
  mobileOpen,
  onToggleCollapsed,
  onMobileOpenChange,
}: {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onMobileOpenChange: (open: boolean) => void;
}) {
  return (
    <>
      <aside
        aria-label="Sidebar"
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-150 lg:flex",
          collapsed ? "w-(--sidebar-rail)" : "w-(--sidebar-width)",
        )}
      >
        <Brand collapsed={collapsed} />
        <div className="flex-1 overflow-y-auto py-2">
          <NavList collapsed={collapsed} />
        </div>
        <div className="border-t border-sidebar-border p-2">
          <Tooltip>
            <TooltipTrigger
              delay={0}
              render={
                <Button
                  variant="ghost"
                  size={collapsed ? "icon-sm" : "sm"}
                  className={cn(
                    "w-full justify-start text-sidebar-foreground/70 hover:text-sidebar-foreground",
                    collapsed && "justify-center",
                  )}
                  onClick={onToggleCollapsed}
                  aria-expanded={!collapsed}
                  aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                />
              }
            >
              {collapsed ? (
                <PanelLeftOpen aria-hidden className="size-4" />
              ) : (
                <>
                  <PanelLeftClose aria-hidden className="size-4" />
                  <span>Collapse</span>
                </>
              )}
            </TooltipTrigger>
            <TooltipContent side="right">
              {collapsed ? "Expand sidebar" : "Collapse sidebar"}
            </TooltipContent>
          </Tooltip>
        </div>
      </aside>

      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-64 gap-0 bg-sidebar p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="border-b border-sidebar-border">
            <Brand collapsed={false} />
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            <NavList collapsed={false} onNavigate={() => onMobileOpenChange(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
