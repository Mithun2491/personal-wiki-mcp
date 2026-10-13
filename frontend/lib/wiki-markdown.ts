const FRONTMATTER_RE = /^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/;

const DUAL_LINK_RE = /\[\[[^\][|]+\|[^\][]+\]\][ \t]*\(?(\[[^\]]+\]\([^)\s]+\))\)?/g;
const PIPE_LINK_RE = /\[\[([^\][|]+)\|([^\][]+)\]\]/g;
const BARE_LINK_RE = /\[\[([^\][|]+)\]\]/g;

export function stripFrontmatter(markdown: string): string {
  return markdown.replace(FRONTMATTER_RE, "");
}

export function normalizeWikiLinks(markdown: string): string {
  return markdown
    .replace(DUAL_LINK_RE, "$1")
    .replace(PIPE_LINK_RE, "[$2]($1)")
    .replace(BARE_LINK_RE, "[$1]($1)");
}

export function prepareWikiMarkdown(markdown: string): string {
  return normalizeWikiLinks(stripFrontmatter(markdown));
}
