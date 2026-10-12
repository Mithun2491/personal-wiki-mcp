"""End-to-end stdio tests: spawn the real server process, speak raw
JSON-RPC over stdin, and prove stdout carries protocol messages only."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from mcp.types.version import LATEST_PROTOCOL_VERSION

PROJECT = Path(__file__).resolve().parents[1]
TIMEOUT = 15.0


class StdioServer:
    """Minimal line-delimited JSON-RPC harness around a spawned server."""

    def __init__(self, root: Path):
        env = dict(os.environ)
        env["WIKI_ROOT"] = str(root)
        self.proc = subprocess.Popen(
            [sys.executable, str(PROJECT / "server.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=str(PROJECT),
            env=env,
        )
        self.stdout_lines: list[str] = []
        self.stderr_lines: list[str] = []
        self.pending: list[dict] = []
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        try:
            for line in self.proc.stdout:
                self.stdout_lines.append(line)
                self._lines.put(line)
        finally:
            self._lines.put(None)

    def _read_stderr(self) -> None:
        for line in self.proc.stderr:
            self.stderr_lines.append(line)

    def send(self, payload: dict) -> None:
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def send_raw(self, text: str) -> None:
        self.proc.stdin.write(text + "\n")
        self.proc.stdin.flush()

    def wait_for_id(self, msg_id: int) -> dict:
        """Return the response with the given id. Every consumed line must
        be valid JSON — that is the stdout-purity assertion."""
        while True:
            for index, item in enumerate(self.pending):
                if item.get("id") == msg_id:
                    return self.pending.pop(index)
            line = self._lines.get(timeout=TIMEOUT)
            if line is None:
                raise AssertionError(
                    "server closed stdout before responding; "
                    f"stderr was: {''.join(self.stderr_lines[-5:])}"
                )
            self.pending.append(json.loads(line))  # raises on non-JSON noise

    def shutdown(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            self.proc.kill()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass


@pytest.fixture
def server(fixture_hub):
    proc = StdioServer(fixture_hub)
    try:
        yield proc
    finally:
        proc.shutdown()


def test_initialize_handshake(server: StdioServer):
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        }
    )
    response = server.wait_for_id(1)
    assert response["result"]["serverInfo"]["name"] == "personal-wiki"
    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    server.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = server.wait_for_id(2)
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert names == {"list_wikis", "get_wiki_index", "search_wiki", "read_article"}


def _initialize(server: StdioServer) -> None:
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        }
    )
    server.wait_for_id(1)
    server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})


def test_tools_call_over_stdio(server: StdioServer):
    _initialize(server)
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "list_wikis", "arguments": {}},
        }
    )
    response = server.wait_for_id(3)
    text = response["result"]["content"][0]["text"]
    assert "demo" in text
    assert "OMEGA" not in text  # outside token never leaks


def test_malformed_requests_do_not_crash_server(server: StdioServer):
    _initialize(server)

    # Unknown method -> JSON-RPC error response, not a crash.
    server.send({"jsonrpc": "2.0", "id": 4, "method": "totally/unknown", "params": {}})
    unknown = server.wait_for_id(4)
    assert "error" in unknown
    assert "result" not in unknown

    # Malformed JSON line: spec allows error reply or graceful close.
    server.send_raw("this is not json {{{")
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "list_wikis", "arguments": {}},
        }
    )
    try:
        follow_up = server.wait_for_id(5)
        assert "result" in follow_up  # server survived the garbage line
    except AssertionError:
        # Server chose the other spec-legal option: close the connection.
        assert server.proc.poll() is not None or not server.stdout_lines[-1:]


def test_stdout_is_pure_jsonrpc_and_stderr_used_for_logs(server: StdioServer):
    _initialize(server)
    server.send(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "read_article",
                "arguments": {"path": "topics/demo/wiki/employment.md"},
            },
        }
    )
    response = server.wait_for_id(9)
    assert response["result"]["content"][0]["text"].startswith("# Employment")

    # Everything consumed from stdout parsed as JSON (wait_for_id asserts
    # this per line); no line was plain text or empty.
    assert all(line.strip() for line in server.stdout_lines)
    for line in server.stdout_lines:
        item = json.loads(line)
        assert "jsonrpc" in item

    # Diagnostics (startup log) went to stderr, not stdout.
    assert any("personal-wiki-mcp" in line for line in server.stderr_lines)


def test_server_exits_cleanly_on_stdin_close(server: StdioServer):
    _initialize(server)
    server.proc.stdin.close()
    try:
        code = server.proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.proc.kill()
        pytest.fail("server did not exit after stdin close")
    assert code in (0, None)
