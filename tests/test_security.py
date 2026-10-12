"""Security tests: traversal, outside-root access, symlink/junction
escapes, environment leakage, and read-only behaviour."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from conftest import (
    OUTSIDE_TOKEN,
    REAL_ARTICLE,
    result_json,
    result_text,
    snapshot_tree,
)

TRAVERSAL_PATHS = [
    "../outside_root.md",
    "..\\outside_root.md",
    "topics/../../outside_root.md",
    "topics/demo/../../../outside_root.md",
    "./outside_root.md",
    ".",
    "..",
]

ABSOLUTE_PATHS = [
    r"C:\Windows\win.ini",
    r"C:\Wiki\log.md",
    "/etc/passwd",
    "\\outside_root.md",
]


@pytest.mark.anyio
@pytest.mark.parametrize("bad", TRAVERSAL_PATHS)
async def test_path_traversal_rejected(client, bad):
    result = await client.call_tool("read_article", {"path": bad})
    assert result.is_error, bad
    msg = result_text(result)
    assert "escapes" in msg or "not contain" in msg or "not allowed" in msg, msg
    assert OUTSIDE_TOKEN not in msg


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ABSOLUTE_PATHS)
async def test_absolute_paths_rejected(client, bad):
    result = await client.call_tool("read_article", {"path": bad})
    assert result.is_error, bad
    assert OUTSIDE_TOKEN not in result_text(result)


@pytest.mark.anyio
async def test_null_byte_rejected(client):
    result = await client.call_tool("read_article", {"path": "a\x00b.md"})
    assert result.is_error
    assert "null byte" in result_text(result)


@pytest.mark.anyio
async def test_alternate_data_stream_colon_rejected(client):
    result = await client.call_tool("read_article", {"path": "log.md:evil"})
    assert result.is_error
    assert "not contain" in result_text(result)


@pytest.mark.anyio
async def test_outside_file_is_unreachable_by_any_string(client, fixture_hub):
    outside = fixture_hub.parent / "outside_root.md"
    assert outside.is_file()  # the threat exists...
    for attempt in (str(outside), str(outside).replace("\\", "/")):
        result = await client.call_tool("read_article", {"path": attempt})
        assert result.is_error
        assert OUTSIDE_TOKEN not in result_text(result)


def _make_junction(link: Path, target: Path) -> bool:
    """Create a directory junction (no admin rights required on Windows)."""
    try:
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0 and link.exists()
    except OSError:
        return False


@pytest.mark.anyio
async def test_junction_escape_rejected_on_read(client, fixture_hub):
    link = fixture_hub / "escape_dir"
    if not _make_junction(link, fixture_hub.parent / "outside"):
        pytest.skip("junction creation not permitted on this system")
    assert (link / "secret.md").is_file()  # reachable at the filesystem layer
    result = await client.call_tool("read_article", {"path": "escape_dir/secret.md"})
    assert result.is_error
    assert "escapes" in result_text(result)
    assert OUTSIDE_TOKEN not in result_text(result)


@pytest.mark.anyio
async def test_search_does_not_leak_through_junction(client, fixture_hub):
    link = fixture_hub / "escape_dir"
    if not _make_junction(link, fixture_hub.parent / "outside"):
        pytest.skip("junction creation not permitted on this system")
    result = await client.call_tool("search_wiki", {"query": OUTSIDE_TOKEN})
    assert not result.is_error
    data = result_json(result)
    assert data["match_count"] == 0
    assert data["matches"] == []
    # No match path or snippet may reference outside content.
    for match in data["matches"]:
        assert OUTSIDE_TOKEN not in match.get("snippet", "")
        assert "outside" not in match.get("path", "")


@pytest.mark.anyio
async def test_outputs_contain_no_env_values_or_absolute_paths(
    client, fixture_hub, canary
):
    calls = [
        ("list_wikis", {}),
        ("get_wiki_index", {}),
        ("get_wiki_index", {"wiki": "demo"}),
        ("search_wiki", {"query": "gamma"}),
        ("search_wiki", {"query": "nothing-matches-zzz"}),
        ("read_article", {"path": "topics/demo/wiki/employment.md"}),
        ("read_article", {"path": "topics/demo/wiki/nope.md"}),
        ("read_article", {"path": "../escape.md"}),
    ]
    for name, args in calls:
        result = await client.call_tool(name, args)
        text = result_text(result)
        assert canary not in text, name
        assert str(fixture_hub) not in text, name
        assert str(Path.home()) not in text, name


@pytest.mark.anyio
async def test_fixture_hub_untouched_by_all_tools(client, fixture_hub):
    before = snapshot_tree(fixture_hub)
    calls = [
        ("list_wikis", {}),
        ("get_wiki_index", {}),
        ("get_wiki_index", {"wiki": "demo"}),
        ("get_wiki_index", {"wiki": "escape"}),
        ("search_wiki", {"query": "gamma"}),
        ("search_wiki", {"query": "gamma", "max_results": 2}),
        ("read_article", {"path": "topics/demo/wiki/employment.md"}),
        ("read_article", {"path": "topics/demo/wiki/big.md"}),
        ("read_article", {"path": "../outside_root.md"}),
        ("read_article", {"path": "notes.txt"}),
    ]
    for name, args in calls:
        await client.call_tool(name, args)
    after = snapshot_tree(fixture_hub)
    assert before == after


@pytest.mark.anyio
async def test_real_hub_is_read_only(real_client):
    root = Path.home() / "wiki"
    if not (root / "wikis.json").is_file():
        pytest.skip("real wiki hub not present")
    before = snapshot_tree(root)

    listed = await real_client.call_tool("list_wikis", {})
    assert not listed.is_error
    assert "personal-records-employment" in result_text(listed)

    idx = await real_client.call_tool(
        "get_wiki_index", {"wiki": "personal-records-employment"}
    )
    assert not idx.is_error
    assert result_text(idx).lstrip().startswith("#")

    if (root / REAL_ARTICLE).is_file():
        article = await real_client.call_tool("read_article", {"path": REAL_ARTICLE})
        assert not article.is_error

    search = await real_client.call_tool("search_wiki", {"query": "employment"})
    assert not search.is_error

    after = snapshot_tree(root)
    assert before == after, "read-only tools modified the real wiki"


def test_source_is_stdio_only_without_network_or_shell():
    """Static audit: no HTTP/network/shell surfaces, stdio transport only."""
    project = Path(__file__).resolve().parents[1]
    source = ""
    for name in ("server.py", "wiki_paths.py"):
        source += (project / name).read_text(encoding="utf-8")
    lowered = source.lower()
    banned = [
        "streamable",
        "run_sse",
        "socket",
        "urllib",
        "requests",
        "http.client",
        "subprocess",
        "os.system",
        "os.popen",
        "eval(",
        "exec(",
        "__import__",
        "shell=True",
    ]
    for token in banned:
        assert token not in lowered, f"banned token found in source: {token}"
    assert 'transport="stdio"' in source


def test_error_messages_never_carry_absolute_paths():
    """Unit-level: wiki_paths errors are absolute-path free."""
    import wiki_paths as wp
    from mcp.server.mcpserver.exceptions import ToolError

    hostile_inputs = [
        r"C:\Windows\win.ini",
        "..\\secret.md",
        "a\x00b.md",
        "",
    ]
    for bad in hostile_inputs:
        try:
            wp.resolve_in_root(bad)
        except ToolError as exc:
            message = str(exc)
            assert "C:\\Users" not in message
            assert str(Path.home()) not in message
        else:
            pytest.fail(f"resolve_in_root accepted {bad!r}")
