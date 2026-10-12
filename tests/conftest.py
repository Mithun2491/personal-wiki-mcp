"""Shared fixtures: a synthetic wiki hub, the in-memory MCP client, and
small helpers reused across the test modules.

Tests never write to the real wiki; the real hub is only ever *read*
(and hash-snapshotted to prove it stays untouched).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

OUTSIDE_TOKEN = "OMEGA-ZETA-OUTSIDE-TOKEN"
CANARY_ENV = "WIKI_MCP_CANARY"
REAL_ARTICLE = "topics/personal-records-employment/wiki/topics/employment-history.md"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fixture_hub(tmp_path: Path) -> Path:
    """Build a small synthetic hub, plus hostile files *outside* it."""
    root = tmp_path / "wiki"
    (root / "topics" / "demo" / "wiki").mkdir(parents=True)
    (root / "topics" / "demo" / "raw").mkdir(parents=True)

    registry = {
        "default": "<HUB>",
        "wikis": {
            "hub": {"path": "<HUB>", "description": "Global knowledge base"},
            "demo": {"path": "topics/demo", "description": "Demo topic", "status": "active"},
            "escape": {"path": "../../outside", "description": "hostile entry", "status": "active"},
        },
        "local_wikis": [],
    }
    (root / "wikis.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    (root / "_index.md").write_text(
        "# Master Index\n\nhub alpha marker line\n", encoding="utf-8"
    )
    (root / "log.md").write_text("2026-10-12: fixture created\n", encoding="utf-8")
    (root / "topics" / "demo" / "_index.md").write_text(
        "# Demo Index\n\ndemo beta marker line\n", encoding="utf-8"
    )
    (root / "topics" / "demo" / "wiki" / "employment.md").write_text(
        "# Employment\n\n"
        "Gamma Corporation was an employer.\n"
        "Some notes about gamma benefits.\n"
        "Unrelated third line.\n",
        encoding="utf-8",
    )
    (root / "topics" / "demo" / "raw" / "note.md").write_text(
        "raw note delta marker\n", encoding="utf-8"
    )
    (root / "notes.txt").write_text("epsilon not markdown\n", encoding="utf-8")
    # Large file: exceeds MAX_RETURN_CHARS so truncation kicks in.
    (root / "topics" / "demo" / "wiki" / "big.md").write_text(
        "gamma repeat line\n" * 3000, encoding="utf-8"
    )

    # Hostile neighbours outside the root (must stay unreachable).
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.md").write_text(f"secret {OUTSIDE_TOKEN}\n", encoding="utf-8")
    (tmp_path / "outside_root.md").write_text(f"loose {OUTSIDE_TOKEN}\n", encoding="utf-8")
    return root


@pytest.fixture
def wiki_env(fixture_hub, monkeypatch):
    monkeypatch.setenv("WIKI_ROOT", str(fixture_hub))


@pytest.fixture
def canary(monkeypatch):
    """Sentinel env value that must never appear in any tool output."""
    value = "CANARY-9f3a-env-value-DO-NOT-LEAK"
    monkeypatch.setenv(CANARY_ENV, value)
    return value


@pytest.fixture
async def client(wiki_env, canary):
    """In-memory MCP client wired to the server (official SDK testing API)."""
    from mcp import Client

    from server import mcp as server_mcp

    async with Client(server_mcp, raise_exceptions=True) as session:
        yield session


@pytest.fixture
async def real_client(monkeypatch):
    """Client using the default root (the real hub at ~/wiki)."""
    from mcp import Client

    from server import mcp as server_mcp

    monkeypatch.delenv("WIKI_ROOT", raising=False)
    async with Client(server_mcp, raise_exceptions=True) as session:
        yield session


def result_text(result) -> str:
    """Flatten a CallToolResult's text contents into one string."""
    parts = [
        block.text
        for block in result.content
        if getattr(block, "type", None) == "text"
    ]
    return "\n".join(parts)


def result_json(result) -> dict:
    return json.loads(result_text(result))


def snapshot_tree(root: Path) -> dict[str, tuple[int, int, str]]:
    """Map every file under root to (size, mtime_ns, sha256)."""
    snap: dict[str, tuple[int, int, str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        stat = path.stat()
        rel = path.relative_to(root).as_posix()
        snap[rel] = (stat.st_size, stat.st_mtime_ns, hashlib.sha256(data).hexdigest())
    return snap
