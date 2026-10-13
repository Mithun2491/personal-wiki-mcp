import {
  BookOpen,
  LayoutGrid,
  Search,
  Settings,
  Library,
} from "lucide-react";

export const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/wikis", label: "Wikis", icon: Library },
  { href: "/search", label: "Search", icon: Search },
  { href: "/article", label: "Reader", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;
