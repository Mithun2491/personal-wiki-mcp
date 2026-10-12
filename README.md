# personal-wiki-mcp

Read-only MCP server for the local LLM wiki hub
(`~/wiki`), built on the official Python MCP SDK.

- **Local transport:** stdio only (`server.py`). No HTTP, no ports, no
  network. Unchanged.
- **Tools:** `list_wikis`, `get_wiki_index`, `search_wiki`, `read_article`.
- **Safety:** every path is resolved (symlinks/junctions followed) and
  required to stay inside the wiki root; only `.md` reads; result counts
  and text sizes are capped; diagnostics go to stderr only; no write,
  shell, or environment-exposing tools.

## Layout

| File | Purpose |
|------|---------|
| `server.py` | MCP server entry point (`MCPServer`, stdio transport) |
| `remote_server.py` | Optional HTTPS entry point for Render (streamable-HTTP + bearer auth) |
| `wiki_paths.py` | Path validation, registry access, read limits |
| `scripts/fetch_private_wiki.py` | Optional start-time fetch of a private wiki snapshot (Render) |
| `deploy-wiki/` | Synthetic sample hub for the Render deploy (no personal data) |
| `tests/` | pytest suite (tools, security, stdio protocol, remote HTTP) |
| `requirements.txt` | Runtime pins (`mcp==2.3.0`, `uvicorn==0.54.0`) |
| `requirements-dev.txt` | Test pins (adds `pytest==9.1.1`) |
| `requirements-lock.txt` | Full tested environment lock |
| `render.yaml` | Render blueprint (free web service, health check, secrets) |
| `DEPLOYMENT.md` | Render deployment, secrets, and security documentation |

## Setup

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Test

```bat
.venv\Scripts\python -m pytest
```

## Run manually (stdio)

```bat
set WIKI_ROOT=%USERPROFILE%\wiki
.venv\Scripts\python server.py
```

`WIKI_ROOT` defaults to `~/wiki` when unset.

## OpenCode registration (pending approval)

```jsonc
"mcp": {
  "personal-wiki": {
    "type": "local",
    "command": [
      "<project-dir>\\.venv\\Scripts\\python.exe",
      "<project-dir>\\server.py"
    ],
    "cwd": "<project-dir>",
    "environment": { "WIKI_ROOT": "<wiki-root>" },
    "enabled": true,
    "timeout": 15000
  }
}
```

## Remote deployment (Render, optional)

`remote_server.py` is a **separate** entry point that serves the same
four read-only tools over streamable-HTTP for Render. It requires a
`MCP_AUTH_TOKEN` bearer token on every `/mcp` request and never touches
the local stdio server. The committed `deploy-wiki/` tree is a synthetic
sample hub — personal wiki data stays out of Git.

```bat
set WIKI_ROOT=.\deploy-wiki
set MCP_AUTH_TOKEN=<32+ random chars>
python remote_server.py
```

Full setup, secrets, health checks, and the private-snapshot option:
[DEPLOYMENT.md](DEPLOYMENT.md).
