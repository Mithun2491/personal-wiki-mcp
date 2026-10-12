"""personal-wiki-mcp — a read-only MCP server for the local LLM wiki hub.

Transport: local stdio only (no HTTP, no ports, no network).
Tools: list_wikis, get_wiki_index, search_wiki, read_article.
All filesystem access goes through wiki_paths, which confines reads to
the canonical wiki root.  Diagnostics go to stderr; stdout carries MCP
protocol messages only.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import wiki_paths as wp

VERSION = "1.0.0"

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

log = logging.getLogger("personal-wiki-mcp")

mcp = MCPServer(
    name="personal-wiki",
    version=VERSION,
    instructions=(
        "Read-only access to the local LLM wiki hub. All file paths are "
        "relative to the wiki root and must stay inside it. This server "
        "cannot write, delete, or execute anything; do not attempt writes."
    ),
)


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


@mcp.tool(annotations=_READ_ONLY)
def list_wikis() -> str:
    """List wikis registered in the hub registry (wikis.json) as JSON.

    Returns each wiki's name, registry path, description, and status.
    Includes the hub itself; the registry ``default`` marks the hub.
    """
    root = wp.get_root()
    registry = wp.load_registry(root)
    wikis = registry.get("wikis")
    if not isinstance(wikis, dict):
        raise ToolError("hub registry has no 'wikis' mapping")
    entries = []
    truncated = False
    for index, (name, entry) in enumerate(wikis.items()):
        if index >= wp.MAX_REGISTRIES:
            truncated = True
            break
        if not isinstance(entry, dict):
            continue
        entries.append(
            {
                "name": name,
                "path": entry.get("path"),
                "description": entry.get("description"),
                "status": entry.get("status", "active"),
                "is_hub": str(entry.get("path", "")) in ("<HUB>", "hub"),
            }
        )
    payload = {
        "default": registry.get("default"),
        "count": len(entries),
        "truncated": truncated,
        "wikis": entries,
    }
    return _dump(payload)


@mcp.tool(annotations=_READ_ONLY)
def get_wiki_index(wiki: str = "") -> str:
    """Return the Markdown index of a wiki: hub index by default, or the
    named wiki's index (see list_wikis for names)."""
    wdir = wp.wiki_dir(wiki)
    index_path = wp.index_file(wdir)
    text, byte_trunc = wp.read_text_file(index_path, wp.MAX_INDEX_BYTES)
    text, char_trunc = wp.truncate_chars(text, wp.MAX_RETURN_CHARS)
    if byte_trunc and not char_trunc:
        text += "\n\n[truncated: index exceeds byte limit]"
    return text


@mcp.tool(annotations=_READ_ONLY)
def search_wiki(
    query: str,
    wiki: str = "",
    max_results: int = wp.DEFAULT_SEARCH_RESULTS,
) -> str:
    """Case-insensitive full-text search over Markdown files in the wiki.

    Args:
        query: Text to look for (max 200 chars, matched per line).
        wiki: Optional wiki name from list_wikis; empty searches the whole hub.
        max_results: Cap on returned matches (1-50).

    Returns JSON with matches (path, line number, snippet) plus scan counts.
    """
    if not isinstance(query, str) or not query.strip():
        raise ToolError("query must be a non-empty string")
    query = query.strip()
    if len(query) > wp.MAX_QUERY_CHARS:
        raise ToolError(f"query must be at most {wp.MAX_QUERY_CHARS} characters")
    try:
        limit = int(max_results)
    except (TypeError, ValueError):
        raise ToolError("max_results must be an integer") from None
    limit = max(1, min(limit, wp.MAX_SEARCH_RESULTS))

    root = wp.get_root()
    scope = wp.wiki_dir(wiki) if wiki else root
    needle = query.casefold()

    matches: list[dict] = []
    files_scanned = 0
    truncated = False
    stop = False
    for rel, path in wp.iter_markdown_files(scope, root):
        files_scanned += 1
        text, _ = wp.read_text_file(path, wp.MAX_SEARCH_FILE_BYTES)
        file_hits = 0
        for line_no, line in enumerate(text.splitlines(), start=1):
            idx = line.casefold().find(needle)
            if idx < 0:
                continue
            if len(matches) >= limit:
                truncated = True
                stop = True
                break
            if file_hits >= wp.MAX_MATCHES_PER_FILE:
                truncated = True
                break  # per-file cap: continue with the next file
            matches.append(
                {
                    "path": rel,
                    "line": line_no,
                    "snippet": _snippet(line, idx, len(query)),
                }
            )
            file_hits += 1
        if stop:
            break

    return _dump(
        {
            "query": query,
            "wiki": wiki or "hub",
            "files_scanned": files_scanned,
            "match_count": len(matches),
            "max_results": limit,
            "truncated": truncated,
            "matches": matches,
        }
    )


def _snippet(line: str, match_idx: int, query_len: int) -> str:
    """Extract a single-line window around the match, capped in size."""
    stripped = line.strip()
    # Position of the match inside the stripped line (approximate but close).
    offset = match_idx - (len(line) - len(line.lstrip()))
    start = max(0, offset - 60)
    end = min(len(stripped), offset + query_len + 140)
    snippet = stripped[start:end].strip()
    if len(snippet) > wp.MAX_SNIPPET_CHARS:
        snippet = snippet[: wp.MAX_SNIPPET_CHARS] + "..."
    if start > 0:
        snippet = "..." + snippet
    if end < len(stripped):
        snippet = snippet + "..."
    return snippet


@mcp.tool(annotations=_READ_ONLY)
def read_article(path: str) -> str:
    """Read one Markdown (.md) file by wiki-relative path.

    Args:
        path: Path relative to the wiki root, e.g.
            'topics/<name>/wiki/topics/<slug>.md'. Absolute paths, '..',
            and non-.md files are rejected.
    """
    target = wp.resolve_in_root(path)
    if target.suffix.lower() != ".md":
        raise ToolError("only Markdown (.md) files can be read")
    if not target.exists():
        raise ToolError(f"file not found: {path.strip()}")
    if target.is_dir():
        raise ToolError(f"path is a directory, not a file: {path.strip()}")
    text, byte_trunc = wp.read_text_file(target, wp.MAX_READ_BYTES)
    text, char_trunc = wp.truncate_chars(text, wp.MAX_RETURN_CHARS)
    if byte_trunc and not char_trunc:
        text += "\n\n[truncated: file exceeds byte limit]"
    return text


def main() -> None:
    """Start the server on local stdio.  Never binds a port."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        wp.get_root()
    except ToolError as exc:
        print(f"personal-wiki-mcp: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    log.info("personal-wiki-mcp %s starting on stdio (read-only)", VERSION)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
