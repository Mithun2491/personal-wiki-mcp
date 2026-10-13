"use client";

import { useRouter } from "next/navigation";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { prepareWikiMarkdown } from "@/lib/wiki-markdown";
import { cn } from "cn";

export function resolveArticlePath(href: string, baseDir: string): string | null {
  const clean = href.split("#")[0].split("?")[0].trim();
  if (!clean || !/\.md$/i.test(clean)) return null;
  if (clean.includes("\\") || clean.includes(":") || clean.includes("\0")) {
    return null;
  }
  const parts = clean.startsWith("/") ? [] : baseDir.split("/").filter(Boolean);
  for (const seg of clean.split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") {
      if (parts.length === 0) return null;
      parts.pop();
    } else {
      parts.push(seg);
    }
  }
  if (parts.length === 0) return null;
  return parts.join("/");
}

function isExternal(href: string): boolean {
  return /^(https?:)?\/\//i.test(href) || /^[a-z][a-z0-9+.-]*:/i.test(href);
}

export function MarkdownView({
  markdown,
  baseDir,
  className,
}: {
  markdown: string;
  baseDir: string;
  className?: string;
}) {
  const router = useRouter();

  const components: Components = {
    h1: ({ children }) => (
      <h1 className="text-section font-semibold text-foreground">{children}</h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-body font-semibold text-foreground">{children}</h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-caption font-semibold text-foreground">{children}</h3>
    ),
    p: ({ children }) => <p className="text-article text-foreground/90">{children}</p>,
    a: ({ href, children }) => {
      if (!href) return <span>{children}</span>;
      if (href.startsWith("#")) {
        return <a href={href}>{children}</a>;
      }
      if (isExternal(href)) {
        return (
          <a href={href} target="_blank" rel="noreferrer">
            {children}
          </a>
        );
      }
      const target = resolveArticlePath(href, baseDir);
      if (!target) return <span className="font-mono">{children}</span>;
      return (
        <button
          type="button"
          onClick={() => router.push(`/article?path=${encodeURIComponent(target)}`)}
          className="cursor-pointer text-left text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
        >
          {children}
        </button>
      );
    },
    ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
    li: ({ children }) => <li className="text-article text-foreground/90">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">
        {children}
      </blockquote>
    ),
    code: ({ children }) => (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
        {children}
      </code>
    ),
    pre: ({ children }) => (
      <pre className="overflow-x-auto rounded-md border border-border bg-muted/40 p-3 text-caption [&>code]:bg-transparent [&>code]:p-0">
        {children}
      </pre>
    ),
    table: ({ children }) => (
      <table className="w-full border-collapse text-caption">{children}</table>
    ),
    th: ({ children }) => (
      <th className="border border-border bg-muted/40 px-2 py-1 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
    hr: () => <hr className="border-border" />,
    img: ({ alt }) => (
      <span className="block rounded-md border border-dashed border-border px-3 py-2 font-mono text-meta text-muted-foreground">
        image unavailable in read-only preview{alt ? `: ${alt}` : ""}
      </span>
    ),
  };

  return (
    <div
      className={cn(
        "space-y-3 overflow-x-auto text-article leading-relaxed [&_a]:text-primary [&_a]:underline [&_a]:decoration-primary/40 [&_a]:underline-offset-2",
        className,
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]} components={components}>
        {prepareWikiMarkdown(markdown)}
      </Markdown>
    </div>
  );
}
