# Deploying to Render (free tier)

This repo ships two entry points:

| Entry point | Transport | Auth | Audience |
|---|---|---|---|
| `server.py` | local stdio | none (your machine) | local MCP clients (OpenCode, etc.) |
| `remote_server.py` | streamable-HTTP on `0.0.0.0:$PORT` | bearer token on **every** `/mcp` request | Render (internet) |

The remote server exposes **only** the same four read-only tools
(`list_wikis`, `get_wiki_index`, `search_wiki`, `read_article`). There is
no write, shell, or arbitrary-file surface, and all filesystem access is
confined to the wiki root by `wiki_paths.py`.

## One-time setup

1. Push this repo to GitHub (it contains **no personal wiki data** — the
   committed `deploy-wiki/` tree is a synthetic sample hub).
2. In Render: **New → Blueprint**, select the repo. `render.yaml` defines
   the free web service.
3. Set the secret environment variables (Blueprint marks them
   `sync: false`, so their values are never read from Git):

   | Variable | Required | Purpose |
   |---|---|---|
   | `MCP_AUTH_TOKEN` | **yes** | Bearer token for every `/mcp` request. Minimum 32 characters; the server refuses to start without one. |
   | `WIKI_SNAPSHOT_URL` | no | `https://` URL of a private `tar.gz` wiki snapshot (see below). |
   | `WIKI_SNAPSHOT_SHA256` | no | Expected sha256 of that snapshot; enforced when set. |
   | `MCP_ALLOWED_HOSTS` | no (set after first deploy) | Comma-separated Host header allowlist, e.g. `your-service.onrender.com`. Enables Host/Origin (DNS-rebinding) validation. |

   `WIKI_ROOT` and `PORT` are set by the blueprint/Render itself — you do
   not need to configure them.

4. Generate a strong token locally and paste it into Render's dashboard
   (never commit it):

   ```bat
   :: PowerShell
   -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
   ```

   ```sh
   # or
   openssl rand -base64 32
   ```

5. Deploy. Render terminates TLS at its edge; the app speaks plain HTTP
   internally and binds `0.0.0.0:$PORT` (Render injects `PORT`,
   default `10000`).

## Connecting an MCP client

Point a streamable-HTTP MCP client at:

```
https://your-service.onrender.com/mcp
```

with header:

```
Authorization: Bearer <MCP_AUTH_TOKEN>
```

Example (any MCP-capable client that supports streamable HTTP + headers).
The server runs in **stateless JSON mode**: each request is independent,
no session handshake is required, and nothing is lost when the free-tier
instance spins down.

## Health checks

`GET /health` is intentionally **unauthenticated** (Render probes cannot
send headers) and returns exactly:

```json
{"status": "ok"}
```

It reveals no wiki names, counts, paths, versions, or environment values.
`render.yaml` sets `healthCheckPath: /health`.

## Wiki content options

### Option A — synthetic sample (default)

The committed `deploy-wiki/` hub is fake content (a registry, an index,
and one demo article). It exists so the deployment is verifiable without
publishing anything personal.

### Option B — private snapshot (optional)

Set `WIKI_SNAPSHOT_URL` (and ideally `WIKI_SNAPSHOT_SHA256`) to a private
`tar.gz` of your wiki hub. At each service start,
`scripts/fetch_private_wiki.py` downloads it into the **ephemeral** disk
and installs it as the wiki root before the server boots.

- The snapshot must contain `wikis.json` at its root (or inside exactly
  one top-level folder).
- The URL must be `https://`. The script never prints the URL, caps the
  download at 100 MiB, verifies the sha256 when provided, and rejects
  archive members with absolute paths, `..`, links, or devices.
- Host the snapshot wherever you already keep private files (a private
  GitHub release asset, an S3 pre-signed URL, etc.). Rotate the URL if it
  leaks — treat it as a credential.

The personal wiki itself still never enters this Git repository.

## Persistence on Render free

**There is no persistent disk and none is needed.**

- The server is **read-only**: it never writes to the wiki, so the
  ephemeral container filesystem is sufficient.
- The wiki content ships *with the deploy* (committed sample, or fetched
  at start from your private snapshot). Each cold start re-reads the same
  bytes.
- Streamable-HTTP runs in **stateless** mode: no in-memory session table
  to lose across Render's free-tier spin-downs (~15 min idle → ~50 s
  cold start).

If you ever add a *write* feature, you would need a paid Render disk or
an external store — deliberately out of scope for this read-only server.

## Security model (summary)

- Every `/mcp` request requires `Authorization: Bearer <MCP_AUTH_TOKEN>`;
  comparison is constant-time (`secrets.compare_digest`) and the server
  fails closed (refuses to boot) if the token is missing or shorter than
  32 characters.
- Only the four read-only tools are registered; the tool catalog is
  asserted in tests and cannot drift.
- All paths are resolved and confined to the wiki root (`wiki_paths.py`);
  traversal, absolute paths, alternate data streams, and null bytes are
  rejected (tested over HTTP too).
- Request bodies are capped at 256 KiB; search/read results are capped.
- After the first deploy, set `MCP_ALLOWED_HOSTS` to your service
  hostname to validate the `Host` header (DNS-rebinding defense).
- Rotate the token by updating the Render env var and restarting the
  service. If a token ever leaks, rotate it immediately.

## Local smoke test (no Render required)

```bat
:: PowerShell — fake wiki + token, then hit the endpoints
$env:WIKI_ROOT = ".\deploy-wiki"
$env:MCP_AUTH_TOKEN = "local-smoke-token-0123456789abcdef0123456789abcdef"
$env:PORT = "8123"
python remote_server.py
```

```bat
:: In another shell
curl http://127.0.0.1:8123/health
curl -X POST http://127.0.0.1:8123/mcp -H "Authorization: Bearer %MCP_AUTH_TOKEN%" -H "Content-Type: application/json" -H "Accept: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
```

A request without the `Authorization` header must return `401`.

## Costs

No paid dependencies or services are introduced:

- Runtime deps are `mcp==2.3.0` (which already includes `uvicorn`,
  `starlette`, and `sse-starlette`) plus an explicit `uvicorn` pin at the
  same version.
- The Render **free** web service tier is used (`plan: free` in
  `render.yaml`). Free instances spin down when idle — expect a cold
  start on the first request after idle periods.

## What never goes in Git

Personal wiki data, CVs, résumés, tokens, secrets, and local absolute
paths. `.gitignore` already excludes `.env*`, keys, `wiki/`, `.wiki/`,
and name-prefixed personal files; `deploy-wiki/` contains only synthetic
content and is explicitly re-included.
