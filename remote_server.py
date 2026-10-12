"""personal-wiki-mcp remote — HTTPS MCP endpoint for Render.

Transport: streamable-HTTP on 0.0.0.0:$PORT (Render injects PORT and
terminates TLS at its edge; this process speaks plain HTTP internally).
Authentication: every /mcp request requires `Authorization: Bearer
<MCP_AUTH_TOKEN>`; the server refuses to start without a strong token.
Tools: the same four read-only tools as the stdio server, imported from
server.py — no writes, no shell, no arbitrary file access, no directory
traversal (all filesystem access still goes through wiki_paths).
Health: GET /health returns only {"status": "ok"} — no wiki data, no
paths, no environment values; unauthenticated so Render probes work.
"""

from __future__ import annotations

import logging
import os
import secrets
import sys

from mcp.server import MCPServer
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.applications import Starlette

import wiki_paths as wp
from server import (
    VERSION,
    _READ_ONLY,
    get_wiki_index,
    list_wikis,
    read_article,
    search_wiki,
)

MIN_TOKEN_LENGTH = 32
DEFAULT_PORT = 10000  # Render's default; overridden by the PORT env var.
MAX_REQUEST_BODY_BYTES = 256 * 1024

log = logging.getLogger("personal-wiki-mcp-remote")


class StaticTokenVerifier:
    """TokenVerifier accepting exactly one shared bearer token.

    Comparison is constant-time (secrets.compare_digest).  A match yields
    the ``read`` scope required by AuthSettings; any mismatch yields None,
    which the SDK's bearer middleware turns into a 401.
    """

    def __init__(self, expected_token: str) -> None:
        self._expected = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(
            token.encode("utf-8", errors="replace"),
            self._expected.encode("utf-8"),
        ):
            return None
        return AccessToken(token=token, client_id="static-client", scopes=["read"])


def _load_token() -> str:
    """Read MCP_AUTH_TOKEN from the environment, fail closed if weak/absent.

    The error message never contains the token value.
    """
    token = os.environ.get("MCP_AUTH_TOKEN", "")
    if len(token) < MIN_TOKEN_LENGTH:
        print(
            "personal-wiki-remote: MCP_AUTH_TOKEN is missing or shorter than "
            f"{MIN_TOKEN_LENGTH} characters; refusing to start",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return token


def _resolve_port() -> int:
    """Read the PORT env var Render injects (default 10000)."""
    raw = os.environ.get("PORT", str(DEFAULT_PORT))
    try:
        port = int(raw)
    except ValueError:
        print("personal-wiki-remote: PORT must be an integer", file=sys.stderr)
        raise SystemExit(1) from None
    if not (0 < port < 65536):
        print("personal-wiki-remote: PORT must be between 1 and 65535", file=sys.stderr)
        raise SystemExit(1)
    return port


def _transport_security() -> TransportSecuritySettings | None:
    """DNS-rebinding protection driven by MCP_ALLOWED_HOSTS.

    Returns None (protection off) when no hosts are configured — the
    default behind Render's TLS-terminating proxy.  When hosts ARE set,
    requests whose Host header does not match are rejected with 421, and
    browser Origin headers are checked against MCP_ALLOWED_ORIGINS
    (defaulting to https://<host> for each allowed host).
    """
    hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if not hosts:
        return None
    origins = [o.strip() for o in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    if not origins:
        origins = [f"https://{h}" for h in hosts]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_server(token: str) -> MCPServer:
    """Build the remote MCPServer: same four read-only tools, auth wired in."""
    mcp = MCPServer(
        name="personal-wiki",
        version=VERSION,
        instructions=(
            "Read-only access to the LLM wiki hub over HTTPS. Every request "
            "must carry a valid bearer token. All file paths are relative to "
            "the wiki root and must stay inside it. This server cannot write, "
            "delete, or execute anything; do not attempt writes."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl("https://auth.invalid/"),
            resource_server_url=None,
            required_scopes=["read"],
        ),
        token_verifier=StaticTokenVerifier(token),
    )

    for fn in (list_wikis, get_wiki_index, search_wiki, read_article):
        mcp.tool(annotations=_READ_ONLY)(fn)

    # Deliberately unauthenticated: Render health probes cannot send
    # headers.  The response is a fixed literal with no wiki data.
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    return mcp


def build_app(token: str) -> Starlette:
    """Construct the Starlette app (streamable-HTTP, JSON, stateless).

    Stateless mode creates a fresh transport per request — no in-memory
    session table to lose across Render free-tier spin-downs/cold starts.
    JSON responses (not SSE) pass cleanly through Render's proxy.
    """
    mcp = create_server(token)
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        max_request_body_size=MAX_REQUEST_BODY_BYTES,
        transport_security=_transport_security(),
        host="0.0.0.0",
    )


def main() -> None:
    """Start the remote server on 0.0.0.0:$PORT.  Never touches stdio."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    token = _load_token()
    try:
        wp.get_root()
    except ToolError as exc:
        print(f"personal-wiki-remote: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    port = _resolve_port()
    log.info(
        "personal-wiki-mcp %s remote starting on 0.0.0.0:%s "
        "(streamable-HTTP, auth required, read-only)",
        VERSION,
        port,
    )
    uvicorn.run(build_app(token), host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
