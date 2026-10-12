# personal-wiki-mcp

Read-only MCP server for the local LLM wiki hub
(`~/wiki`), built on the official Python MCP SDK.

- **Transport:** local stdio only. No HTTP server, no ports, no network.
- **Tools:** `list_wikis`, `get_wiki_index`, `search_wiki`, `read_article`.
- **Safety:** every path is resolved (symlinks/junctions followed) and
  required to stay inside the wiki root; only `.md` reads; result counts
  and text sizes are capped; diagnostics go to stderr only; no write,
  shell, or environment-exposing tools.

## Layout

| File | Purpose |
|------|---------|
| `server.py` | MCP server entry point (`MCPServer`, stdio transport) |
| `wiki_paths.py` | Path validation, registry access, read limits |
| `tests/` | pytest suite (tools, security, stdio protocol) |
| `requirements.txt` | Runtime pins (`mcp==2.3.0`) |
| `requirements-dev.txt` | Test pins (adds `pytest==9.1.1`) |
| `requirements-lock.txt` | Full tested environment lock |

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
