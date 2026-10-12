"""Happy-path coverage plus malformed-request handling for all four tools."""

from __future__ import annotations

import pytest
from conftest import result_json, result_text


@pytest.mark.anyio
async def test_list_wikis_returns_registry(client, fixture_hub, canary):
    result = await client.call_tool("list_wikis", {})
    assert not result.is_error
    data = result_json(result)
    names = {w["name"] for w in data["wikis"]}
    assert names == {"hub", "demo", "escape"}
    assert data["default"] == "<HUB>"
    assert data["truncated"] is False
    demo = next(w for w in data["wikis"] if w["name"] == "demo")
    assert demo["path"] == "topics/demo"
    assert demo["is_hub"] is False
    text = result_text(result)
    assert str(fixture_hub) not in text
    assert canary not in text


@pytest.mark.anyio
async def test_get_index_hub_default(client):
    result = await client.call_tool("get_wiki_index", {})
    assert not result.is_error
    assert "# Master Index" in result_text(result)


@pytest.mark.anyio
async def test_get_index_hub_by_name(client):
    result = await client.call_tool("get_wiki_index", {"wiki": "hub"})
    assert not result.is_error
    assert "# Master Index" in result_text(result)


@pytest.mark.anyio
async def test_get_index_named_wiki(client):
    result = await client.call_tool("get_wiki_index", {"wiki": "demo"})
    assert not result.is_error
    assert "# Demo Index" in result_text(result)


@pytest.mark.anyio
async def test_get_index_unknown_wiki(client):
    result = await client.call_tool("get_wiki_index", {"wiki": "nope"})
    assert result.is_error
    assert "unknown wiki" in result_text(result)


@pytest.mark.anyio
async def test_get_index_hostile_registry_entry_rejected(client):
    result = await client.call_tool("get_wiki_index", {"wiki": "escape"})
    assert result.is_error
    assert ".." in result_text(result)


@pytest.mark.anyio
async def test_search_finds_matches_with_paths_and_snippets(client):
    result = await client.call_tool("search_wiki", {"query": "corporation"})
    assert not result.is_error
    data = result_json(result)
    assert data["match_count"] >= 1
    for match in data["matches"]:
        assert match["path"].endswith(".md")
        assert not match["path"].startswith("/")
        assert ":" not in match["path"]
        assert isinstance(match["line"], int)
        assert match["snippet"]
    assert any(
        m["path"] == "topics/demo/wiki/employment.md" for m in data["matches"]
    )
    assert "Gamma" in result_text(result)  # snippets preserve original casing


@pytest.mark.anyio
async def test_search_respects_max_results_cap(client):
    result = await client.call_tool(
        "search_wiki", {"query": "gamma", "max_results": 2}
    )
    assert not result.is_error
    data = result_json(result)
    assert data["match_count"] <= 2
    assert data["max_results"] == 2
    assert data["truncated"] is True


@pytest.mark.anyio
async def test_search_max_results_clamped_to_ceiling(client):
    result = await client.call_tool(
        "search_wiki", {"query": "gamma", "max_results": 9999}
    )
    assert not result.is_error
    data = result_json(result)
    assert data["max_results"] == 50


@pytest.mark.anyio
async def test_search_no_match_is_not_an_error(client):
    result = await client.call_tool("search_wiki", {"query": "zzz-not-present-zzz"})
    assert not result.is_error
    data = result_json(result)
    assert data["match_count"] == 0
    assert data["matches"] == []


@pytest.mark.anyio
async def test_search_scoped_to_named_wiki(client):
    scoped = await client.call_tool("search_wiki", {"query": "delta", "wiki": "demo"})
    assert result_json(scoped)["match_count"] == 1
    miss = await client.call_tool("search_wiki", {"query": "alpha", "wiki": "demo"})
    assert result_json(miss)["match_count"] == 0
    whole = await client.call_tool("search_wiki", {"query": "alpha"})
    assert result_json(whole)["match_count"] >= 1


@pytest.mark.anyio
async def test_search_empty_query_rejected(client):
    result = await client.call_tool("search_wiki", {"query": "   "})
    assert result.is_error
    assert "non-empty" in result_text(result)


@pytest.mark.anyio
async def test_search_query_too_long_rejected(client):
    result = await client.call_tool("search_wiki", {"query": "x" * 500})
    assert result.is_error
    assert "at most" in result_text(result)


@pytest.mark.anyio
async def test_read_article_ok(client):
    result = await client.call_tool(
        "read_article", {"path": "topics/demo/wiki/employment.md"}
    )
    assert not result.is_error
    assert "Gamma Corporation was an employer." in result_text(result)


@pytest.mark.anyio
async def test_read_article_is_case_insensitive_on_extension(client):
    result = await client.call_tool(
        "read_article", {"path": "topics/demo/wiki/employment.MD"}
    )
    assert not result.is_error


@pytest.mark.anyio
async def test_read_article_rejects_non_markdown(client):
    for bad in ("notes.txt", "wikis.json", "topics/demo/wiki/big.md.bak"):
        result = await client.call_tool("read_article", {"path": bad})
        assert result.is_error, bad
        assert ".md" in result_text(result)


@pytest.mark.anyio
async def test_read_article_missing_file(client):
    result = await client.call_tool(
        "read_article", {"path": "topics/demo/wiki/nope.md"}
    )
    assert result.is_error
    assert "not found" in result_text(result)


@pytest.mark.anyio
async def test_read_article_truncates_large_file(client):
    result = await client.call_tool(
        "read_article", {"path": "topics/demo/wiki/big.md"}
    )
    assert not result.is_error
    text = result_text(result)
    assert "[truncated" in text
    assert len(text) <= 41_000


@pytest.mark.anyio
async def test_malformed_missing_required_argument(client):
    result = await client.call_tool("read_article", {})
    assert result.is_error
    assert "error" in result_text(result).lower()


@pytest.mark.anyio
async def test_malformed_wrong_argument_type(client):
    result = await client.call_tool("read_article", {"path": 123})
    assert result.is_error
    assert "error" in result_text(result).lower()


@pytest.mark.anyio
async def test_malformed_wrong_type_on_optional_argument(client):
    result = await client.call_tool("get_wiki_index", {"wiki": 42})
    assert result.is_error


@pytest.mark.anyio
async def test_malformed_empty_path(client):
    result = await client.call_tool("read_article", {"path": ""})
    assert result.is_error
    assert "empty" in result_text(result)


@pytest.mark.anyio
async def test_malformed_unknown_tool_never_succeeds(client):
    from mcp import MCPError

    try:
        result = await client.call_tool(
            "write_article", {"path": "x.md", "content": "y"}
        )
    except MCPError:
        return  # protocol-level rejection is acceptable
    assert result.is_error  # a tool error result is also acceptable


@pytest.mark.anyio
async def test_tool_catalog_is_exactly_four_read_only_tools(client):
    from server import mcp as server_mcp

    tools = await server_mcp.list_tools()
    names = sorted(tool.name for tool in tools)
    assert names == [
        "get_wiki_index",
        "list_wikis",
        "read_article",
        "search_wiki",
    ]
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name
