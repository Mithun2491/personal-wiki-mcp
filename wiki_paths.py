"""Path safety and hub-registry access for the personal wiki MCP server.

Every filesystem access initiated by an MCP tool must go through this
module.  Requested paths are validated against the canonical, symlink-
resolved wiki root; anything that escapes the root is rejected.  Error
messages never contain absolute paths or environment values.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_WIKI_ROOT = str(Path.home() / "wiki")

# Output and traversal limits (defense in depth against oversized reads).
MAX_REGISTRIES = 50
MAX_READ_BYTES = 512 * 1024
MAX_RETURN_CHARS = 40_000
MAX_INDEX_BYTES = 256 * 1024
MAX_SEARCH_FILE_BYTES = 256 * 1024
MAX_SEARCH_RESULTS = 50
DEFAULT_SEARCH_RESULTS = 20
MAX_MATCHES_PER_FILE = 5
MAX_FILES_SCANNED = 2000
MAX_QUERY_CHARS = 200
MAX_SNIPPET_CHARS = 200


def get_root() -> Path:
    """Resolve and validate the canonical wiki root.

    Source: environment variable ``WIKI_ROOT`` if set, else ``~/wiki``.
    Raises ToolError if the root is missing, unreadable, or not a directory.
    """
    raw = os.environ.get("WIKI_ROOT") or DEFAULT_WIKI_ROOT
    candidate = Path(raw).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        raise ToolError("wiki root is unavailable (missing or unreadable)") from None
    if not resolved.is_dir():
        raise ToolError("wiki root is unavailable (not a directory)")
    return resolved


def _ensure_under(root: Path, target: Path) -> Path:
    """Resolve ``target`` (following symlinks/junctions) and require it to
    stay inside ``root``.  Returns the resolved path or raises ToolError."""
    try:
        resolved = target.resolve()
    except (OSError, RuntimeError, ValueError):
        raise ToolError("path could not be resolved") from None
    root_norm = os.path.normcase(str(root))
    path_norm = os.path.normcase(str(resolved))
    within_norm = path_norm == root_norm or path_norm.startswith(root_norm + os.sep)
    if not within_norm or not resolved.is_relative_to(root):
        raise ToolError("path escapes the wiki root")
    return resolved


def resolve_in_root(rel: str) -> Path:
    """Validate a wiki-relative path and return it resolved under the root.

    Rejects: non-strings, empty paths, null bytes, drive letters, NTFS
    alternate data streams (``:``), absolute paths, ``.``/``..`` segments,
    empty segments, and anything that resolves outside the wiki root
    (including via symlinks or junctions).
    """
    if not isinstance(rel, str):
        raise ToolError("path must be a string")
    rel = rel.strip()
    if not rel:
        raise ToolError("path must not be empty")
    if "\x00" in rel:
        raise ToolError("path contains a null byte")
    normalized = rel.replace("\\", "/")
    if ":" in normalized:
        raise ToolError("path must not contain ':' (drive letters and alternate data streams are not allowed)")
    if normalized.startswith("/"):
        raise ToolError("absolute paths are not allowed")
    segments = normalized.split("/")
    if any(seg in ("", ".", "..") for seg in segments):
        raise ToolError("path must not contain empty, '.' or '..' segments")
    root = get_root()
    return _ensure_under(root, root.joinpath(*segments))


def load_registry(root: Path) -> dict:
    """Parse the hub registry ``wikis.json``.  Raises ToolError on any
    missing or malformed registry."""
    reg_path = root / "wikis.json"
    if not reg_path.is_file():
        raise ToolError("hub registry not found (wikis.json)")
    try:
        data = json.loads(reg_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolError(f"hub registry is unreadable: {exc}") from None
    if not isinstance(data, dict):
        raise ToolError("hub registry has invalid structure")
    return data


def wiki_dir(wiki: str) -> Path:
    """Resolve a registered wiki name to a validated directory under root.

    Empty string or ``"hub"`` selects the hub itself.  Registry paths are
    validated exactly like user-supplied paths, so a hostile registry entry
    cannot point outside the root.
    """
    root = get_root()
    if not isinstance(wiki, str) or not wiki.strip() or wiki.strip() == "hub":
        return root
    name = wiki.strip()
    registry = load_registry(root)
    wikis = registry.get("wikis")
    if not isinstance(wikis, dict) or name not in wikis:
        raise ToolError(f"unknown wiki: {name!r}")
    entry = wikis[name]
    path_val = entry.get("path") if isinstance(entry, dict) else None
    if not isinstance(path_val, str) or not path_val.strip():
        raise ToolError(f"wiki {name!r} has no valid path in the registry")
    if path_val.strip() in ("<HUB>", "hub"):
        return root
    resolved = resolve_in_root(path_val)
    if not resolved.is_dir():
        raise ToolError(f"wiki directory missing for {name!r}")
    return resolved


def index_file(wdir: Path) -> Path:
    """Return the validated index file (``_index.md`` or ``index.md``)
    for a wiki directory."""
    root = get_root()
    for name in ("_index.md", "index.md"):
        candidate = wdir / name
        if candidate.is_file():
            return _ensure_under(root, candidate)
    raise ToolError("wiki index not found (_index.md)")


def read_text_file(path: Path, max_bytes: int) -> tuple[str, bool]:
    """Read at most ``max_bytes`` from ``path`` as UTF-8 (errors replaced).

    Returns ``(text, truncated)``.  OSError becomes a ToolError whose
    message carries no filesystem path.
    """
    try:
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        reason = getattr(exc, "strerror", None) or "read error"
        raise ToolError(f"file could not be read: {reason}") from None
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    return text, truncated


def truncate_chars(text: str, limit: int) -> tuple[str, bool]:
    """Cap text at ``limit`` characters, appending a marker when cut."""
    if len(text) <= limit:
        return text, False
    marker = f"\n\n[truncated: showing first {limit} of {len(text)} characters]"
    return text[:limit] + marker, True


def iter_markdown_files(scope: Path, root: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(relpath, resolved_path)`` for Markdown files under ``scope``.

    Walks without following directory symlinks, caps the file count, skips
    hidden directories, and silently skips any file whose resolved location
    escapes ``root`` (symlink/junction escapes).
    """
    count = 0
    for dirpath, dirnames, filenames in os.walk(scope, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not filename.lower().endswith(".md"):
                continue
            full = Path(dirpath) / filename
            try:
                resolved = _ensure_under(root, full)
            except ToolError:
                continue
            if not resolved.is_file():
                continue
            try:
                rel = resolved.relative_to(root).as_posix()
            except ValueError:
                continue
            yield rel, resolved
            count += 1
            if count >= MAX_FILES_SCANNED:
                return
