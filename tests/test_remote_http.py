"""Remote HTTPS tests: bearer authentication, tool behavior over HTTP,
path traversal across the wire, unauthorized requests, health-check
surface, fail-closed startup, live bind, and a static source audit.

Uses Starlette's TestClient against the real streamable-HTTP app (same
code path Render exercises) plus one live-subprocess bind test.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import anyio
import pytest
from conftest import OUTSIDE_TOKEN, canary, fixture_hub, result_json, result_text, wiki_env  # noqa: F401
from mcp.types.version import LATEST_PROTOCOL_VERSION
from starlette.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]

# >= MIN_TOKEN_LENGTH (32); never a real credential.
TEST_TOKEN = "test-token-0123456789abcdef0123456789abcdef"

TOOL_NAMES = {"list_wikis", "get_wiki_index", "search_wiki", "read_article"}

HTTP_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

TRAVERSAL_PATHS = [
    "../outside_root.md",
    "..\\outside_root.md",
    "topics/../../outside_root.md",
    "./outside_root.md",
    ".",
    "..",
]

ABSOLUTE_PATHS = [
    r"C:\Windows\win.ini",
    "/etc/passwd",
    "\\outside_root.md",
]


def _auth(token: str = TEST_TOKEN) -> dict:
    return {**HTTP_HEADERS, "Authorization": f"Bearer {token}"}


def _rpc(payload: dict, headers: dict) -> dict:
    return {"json": payload, "headers": headers}


@pytest.fixture
def remote_app(wiki_env, canary):  # noqa: F811
    """The real remote Starlette app, built against the fixture hub."""
    import remote_server

    return remote_server.build_app(TEST_TOKEN)


@pytest.fixture
def remote(remote_app):
    with TestClient(remote_app) as client:
        yield client


def _post(client: TestClient, payload: dict, headers: dict):
    return client.post("/mcp", json=payload, headers=headers)


def _initialize(client: TestClient, headers: dict, msg_id: int = 1) -> dict:
    response = _post(
        client,
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
        headers,
    )
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_mcp_rejects_missing_authorization(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        HTTP_HEADERS,
    )
    assert response.status_code == 401
    assert "www-authenticate" in response.headers


def test_mcp_rejects_wrong_token(remote, canary):  # noqa: F811
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        _auth("wrong-token-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"),
    )
    assert response.status_code == 401
    body = response.text
    assert canary not in body
    assert "test-token" not in body  # the real token is never echoed


def test_mcp_rejects_wrong_scheme(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {**HTTP_HEADERS, "Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401


def test_mcp_rejects_empty_bearer(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {**HTTP_HEADERS, "Authorization": "Bearer "},
    )
    assert response.status_code == 401


def test_mcp_get_requires_auth(remote):
    response = remote.get("/mcp", headers=HTTP_HEADERS)
    assert response.status_code == 401


def test_mcp_accepts_valid_token_and_lists_exactly_four_tools(remote):
    body = _initialize(remote, _auth())
    assert body["result"]["serverInfo"]["name"] == "personal-wiki"
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        _auth(),
    )
    assert response.status_code == 200
    tools = response.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == TOOL_NAMES
    for tool in tools:
        annotations = tool.get("annotations") or {}
        assert annotations.get("readOnlyHint") is True, tool["name"]
        assert annotations.get("destructiveHint") is False, tool["name"]


def test_remote_catalog_is_identical_to_stdio_catalog():
    """The HTTP surface exposes exactly the stdio server's tool set."""
    from server import mcp as stdio_mcp

    stdio_names = sorted(tool.name for tool in anyio.run(stdio_mcp.list_tools))
    app_token = TEST_TOKEN
    import remote_server

    with TestClient(remote_server.build_app(app_token)) as client:
        response = _post(
            client,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            _auth(),
        )
        remote_names = sorted(tool["name"] for tool in response.json()["result"]["tools"])
    assert remote_names == stdio_names == sorted(TOOL_NAMES)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_is_public_and_data_free(remote, fixture_hub, canary):  # noqa: F811
    response = remote.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    body = response.text
    assert canary not in body
    assert str(fixture_hub) not in body
    assert "wiki" not in body.lower().replace("status", "").replace("ok", "")


# ---------------------------------------------------------------------------
# Tool behavior over HTTP
# ---------------------------------------------------------------------------


def test_list_wikis_over_http(remote, fixture_hub, canary):  # noqa: F811
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "list_wikis", "arguments": {}}},
        _auth(),
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["isError"] is not True
    text = result["content"][0]["text"]
    data = json.loads(text)
    names = {w["name"] for w in data["wikis"]}
    assert names == {"hub", "demo", "escape"}
    assert str(fixture_hub) not in text
    assert canary not in text


def test_get_wiki_index_over_http(remote):
    for wiki, marker in (("", "# Master Index"), ("demo", "# Demo Index")):
        response = _post(
            remote,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "get_wiki_index", "arguments": {"wiki": wiki}}},
            _auth(),
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["isError"] is not True
        assert marker in result["content"][0]["text"]


def test_search_and_read_over_http(remote):
    search = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "search_wiki", "arguments": {"query": "corporation"}}},
        _auth(),
    )
    data = json.loads(search.json()["result"]["content"][0]["text"])
    assert data["match_count"] >= 1
    assert any(m["path"] == "topics/demo/wiki/employment.md" for m in data["matches"])

    read = _post(
        remote,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "read_article",
                    "arguments": {"path": "topics/demo/wiki/employment.md"}}},
        _auth(),
    )
    text = read.json()["result"]["content"][0]["text"]
    assert "Gamma Corporation was an employer." in text


def test_stateless_requests_work_without_initialize(remote):
    """Stateless JSON mode: each POST is independent; no session dance."""
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "list_wikis", "arguments": {}}},
        _auth(),
    )
    assert response.status_code == 200
    assert response.json()["result"]["isError"] is not True


def test_unknown_tool_over_http_is_error_not_crash(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "write_article", "arguments": {"path": "x.md", "content": "y"}}},
        _auth(),
    )
    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True


def test_fixture_hub_untouched_by_remote_tools(remote, fixture_hub):
    from conftest import snapshot_tree

    before = snapshot_tree(fixture_hub)
    calls = [
        {"name": "list_wikis", "arguments": {}},
        {"name": "get_wiki_index", "arguments": {"wiki": "demo"}},
        {"name": "search_wiki", "arguments": {"query": "gamma"}},
        {"name": "read_article", "arguments": {"path": "topics/demo/wiki/employment.md"}},
        {"name": "read_article", "arguments": {"path": "../outside_root.md"}},
    ]
    for index, params in enumerate(calls):
        _post(remote, {"jsonrpc": "2.0", "id": index + 1, "method": "tools/call", "params": params}, _auth())
    after = snapshot_tree(fixture_hub)
    assert before == after


# ---------------------------------------------------------------------------
# Invalid paths over the wire
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", TRAVERSAL_PATHS)
def test_traversal_rejected_over_http(remote, bad):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "read_article", "arguments": {"path": bad}}},
        _auth(),
    )
    result = response.json()["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert OUTSIDE_TOKEN not in text


@pytest.mark.parametrize("bad", ABSOLUTE_PATHS)
def test_absolute_paths_rejected_over_http(remote, bad):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "read_article", "arguments": {"path": bad}}},
        _auth(),
    )
    result = response.json()["result"]
    assert result["isError"] is True
    assert OUTSIDE_TOKEN not in result["content"][0]["text"]


def test_null_byte_rejected_over_http(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "read_article", "arguments": {"path": "a\x00b.md"}}},
        _auth(),
    )
    result = response.json()["result"]
    assert result["isError"] is True
    assert "null byte" in result["content"][0]["text"]


def test_non_markdown_rejected_over_http(remote):
    for bad in ("notes.txt", "wikis.json"):
        response = _post(
            remote,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "read_article", "arguments": {"path": bad}}},
            _auth(),
        )
        result = response.json()["result"]
        assert result["isError"] is True, bad


def test_hostile_registry_entry_rejected_over_http(remote):
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "get_wiki_index", "arguments": {"wiki": "escape"}}},
        _auth(),
    )
    result = response.json()["result"]
    assert result["isError"] is True
    assert OUTSIDE_TOKEN not in result["content"][0]["text"]


# ---------------------------------------------------------------------------
# Unauthorized surface & transport limits
# ---------------------------------------------------------------------------


def test_unknown_path_returns_404_without_leaking_data(remote, canary):  # noqa: F811
    response = remote.get("/definitely-not-a-route")
    assert response.status_code == 404
    assert canary not in response.text


def test_oversized_body_rejected(remote):
    huge = "x" * (300 * 1024)
    response = _post(
        remote,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "search_wiki", "arguments": {"query": huge}}},
        _auth(),
    )
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Fail-closed startup (subprocess)
# ---------------------------------------------------------------------------


def _run_remote(extra_env: dict, fixture_hub: Path, remove: tuple = ()) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["WIKI_ROOT"] = str(fixture_hub)
    env["PYTHONUNBUFFERED"] = "1"
    for key in remove:
        env.pop(key, None)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(PROJECT / "remote_server.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(PROJECT),
    )


def test_startup_refuses_missing_token(fixture_hub):
    proc = _run_remote({}, fixture_hub, remove=("MCP_AUTH_TOKEN",))
    assert proc.returncode == 1
    assert "MCP_AUTH_TOKEN" in proc.stderr
    assert str(fixture_hub) not in proc.stderr


def test_startup_refuses_short_token(fixture_hub, canary):  # noqa: F811
    weak_token = "xyzabc123"  # distinctive value that must never be echoed
    proc = _run_remote({"MCP_AUTH_TOKEN": weak_token}, fixture_hub)
    assert proc.returncode == 1
    assert "MCP_AUTH_TOKEN" in proc.stderr
    assert weak_token not in proc.stderr  # the rejected value is never echoed
    assert canary not in proc.stderr


def test_startup_refuses_missing_wiki_root(fixture_hub):
    env_token = "startup-token-0123456789abcdef0123456789"
    proc = _run_remote({"MCP_AUTH_TOKEN": env_token, "WIKI_ROOT": str(fixture_hub / "nope")}, fixture_hub)
    assert proc.returncode == 1
    assert "wiki root is unavailable" in proc.stderr
    assert env_token not in proc.stderr


def test_startup_refuses_invalid_port(fixture_hub):
    proc = _run_remote(
        {"MCP_AUTH_TOKEN": "startup-token-0123456789abcdef0123456789", "PORT": "not-a-port"},
        fixture_hub,
    )
    assert proc.returncode == 1
    assert "PORT" in proc.stderr


# ---------------------------------------------------------------------------
# Live bind smoke test (the Render contract: 0.0.0.0:$PORT)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_live_server_binds_port_and_enforces_auth(fixture_hub):
    port = _free_port()
    token = "live-token-0123456789abcdef0123456789abcdef"
    env = dict(os.environ)
    env.update(
        {
            "WIKI_ROOT": str(fixture_hub),
            "MCP_AUTH_TOKEN": token,
            "PORT": str(port),
            "PYTHONUNBUFFERED": "1",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT / "remote_server.py")],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(PROJECT),
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 30
        last_error: Exception | None = None
        while time.time() < deadline:
            if proc.poll() is not None:
                _, stderr = proc.communicate(timeout=5)
                pytest.fail(f"remote server exited early: {stderr[-2000:]}")
            try:
                with urllib.request.urlopen(base + "/health", timeout=2) as response:
                    if response.status == 200:
                        assert json.loads(response.read()) == {"status": "ok"}
                        break
            except Exception as exc:  # noqa: BLE001 - startup race, retry
                last_error = exc
                time.sleep(0.3)
        else:
            pytest.fail(f"remote server never became healthy: {last_error}")

        # Unauthenticated MCP request over real HTTP -> 401.
        unauth = urllib.request.Request(
            base + "/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
            headers=HTTP_HEADERS,
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(unauth, timeout=5)
        assert excinfo.value.code == 401

        # Authenticated tools/list over real HTTP -> exactly four tools.
        authed = urllib.request.Request(
            base + "/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}).encode(),
            headers=_auth(token),
            method="POST",
        )
        with urllib.request.urlopen(authed, timeout=10) as response:
            assert response.status == 200
            payload = json.loads(response.read())
        names = {tool["name"] for tool in payload["result"]["tools"]}
        assert names == TOOL_NAMES
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


# ---------------------------------------------------------------------------
# Static source audit
# ---------------------------------------------------------------------------


def test_remote_source_is_auth_gated_without_shell_or_writes():
    """Static audit: remote_server.py has bearer auth, no shell, no writes."""
    source = (PROJECT / "remote_server.py").read_text(encoding="utf-8")
    lowered = source.lower()
    banned = [
        "subprocess",
        "os.system",
        "os.popen",
        "eval(",
        "exec(",
        "__import__",
        "shell=True",
        "pickle",
        "marshal",
        "write_text",
        "write_bytes",
        "shutil",
        "pathlib",
    ]
    for token in banned:
        assert token not in lowered, f"banned token found in remote_server.py: {token}"
    assert "open(" not in lowered  # no file handles at all
    # Bearer auth wiring.
    assert "compare_digest" in source
    assert "MCP_AUTH_TOKEN" in source
    assert "StaticTokenVerifier" in source
    # Render binding contract.
    assert '"0.0.0.0"' in source
    assert '"PORT"' in source
    # Health route is a fixed literal.
    assert '"/health"' in source
    assert '{"status": "ok"}' in source
    # Single source of truth for tools.
    assert "from server import" in source
