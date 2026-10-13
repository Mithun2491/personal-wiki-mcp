# Session Notes — Render Remote MCP Implementation

**Date:** 2026-10-13
**Repo:** `personal-wiki-mcp` (`https://github.com/Mithun2491/personal-wiki-mcp.git`)
**Outcome:** Complete — implemented, reviewed, tested (93/93), committed `92f7153`, pushed to `origin/main`.

---

## 1. Goal

Prepare the existing read-only personal-wiki MCP server (local stdio, 4 tools) for a
future free-tier Render deployment by adding a **separate authenticated streamable-HTTP
endpoint**, without changing the local stdio behavior at all.

Hard constraints honored throughout:
- `server.py` and `wiki_paths.py` remain byte-identical (existing static-audit test bans
  HTTP/shell/network tokens in those files).
- No personal wiki data, CVs, tokens, secret URLs, or absolute personal paths in Git.
- No paid dependencies or services; server never exposes writes/shell/arbitrary file access.
- No deploy during the session; push only after explicit approval.

## 2. Architecture

| Entry point | Transport | Auth | Status |
|---|---|---|---|
| `server.py` | local stdio | n/a (local process) | **unchanged** |
| `remote_server.py` | streamable-HTTP on `0.0.0.0:$PORT` | mandatory `MCP_AUTH_TOKEN` bearer (32+ chars, `secrets.compare_digest`) | new |

Key design decisions:
- Same 4 read-only tools (`list_wikis`, `get_wiki_index`, `search_wiki`, `read_article`)
  re-registered from `server.py` onto a second `MCPServer` — single source of truth.
- **Stateless JSON mode** (`stateless_http=True`, `json_response=True`) — survives Render
  free-tier spin-downs; `tools/call` works without a prior `initialize`.
- `/health` via `@mcp.custom_route` (bypasses auth middleware) returns exactly
  `{"status": "ok"}` — zero data leak, usable as Render `healthCheckPath`.
- Fail-closed startup: refuses to boot if `MCP_AUTH_TOKEN` missing/short; never echoes it.
- 256 KiB request-body cap; DNS-rebinding protection driven by `MCP_ALLOWED_HOSTS`
  (unset at first deploy = off; set post-deploy).
- `AuthSettings` with `issuer_url="https://auth.invalid/"` (RFC 2606 placeholder) and
  no OAuth routes mounted.
- Optional `scripts/fetch_private_wiki.py`: https-only private snapshot fetch at startup
  (sha256 pinning, tar-traversal rejection, secret-URL never printed, 100 MiB / 120 s caps,
  stdlib-only). No-op when `WIKI_SNAPSHOT_URL` unset.

## 3. Files added / changed (commit 92f7153, 15 files, +1392/−3)

**New:**
- `remote_server.py` — Render HTTP entry point (195 lines)
- `scripts/fetch_private_wiki.py` — optional private-snapshot fetcher (165 lines)
- `render.yaml` — free-tier blueprint: `healthCheckPath: /health`, secrets `sync: false`
  (`MCP_AUTH_TOKEN`, `WIKI_SNAPSHOT_URL`, `WIKI_SNAPSHOT_SHA256`, `MCP_ALLOWED_HOSTS`),
  `WIKI_ROOT=./deploy-wiki`, `PYTHON_VERSION=3.12.0`, region oregon
- `.python-version` — pins 3.12.0 (matches tested venv)
- `deploy-wiki/` — **synthetic** sample hub (wikis.json, _index.md, log.md, sample topic
  with one demo article containing the sentinel phrase "deployment sentinel")
- `tests/test_remote_http.py` — 34 tests: 401 on missing/wrong tokens, exact tool-catalog
  match vs stdio, traversal/absolute/null-byte rejection over the wire, health
  data-freeness, fail-closed startup, live subprocess bind smoke test, static source audit
- `tests/test_fetch_private_wiki.py` — 9 tests: https-only, tar traversal, sha256 mismatch,
  URL-never-echoed, stdlib-only AST audit
- `DEPLOYMENT.md` — full setup: token generation, client connection, wiki content options
  A (committed sample) / B (private snapshot), persistence rationale, security model,
  local smoke test, costs, Git exclusions

**Modified:**
- `.gitignore` — +5 lines: `!deploy-wiki/`, `!deploy-wiki/**` negations (the existing
  `wiki/` pattern would otherwise ignore it)
- `README.md` — clarified local-transport wording, layout table, new "Remote deployment"
  section pointing to DEPLOYMENT.md
- `requirements.txt` — +`uvicorn==0.54.0` explicit pin (already transitive via `mcp==2.3.0`;
  lockfile verified unchanged — zero new packages)

**Untouched (verified byte-identical):** `server.py`, `wiki_paths.py`, all pre-existing
tests, `requirements-lock.txt`.

## 4. Verification

- **Test suite: 93/93 passing** (49 existing + 34 remote + 9 fetch + 1 audit).
- Live spike confirmed: health 200, no-auth/wrong-token 401, good-token 200 with exactly
  the four tool names, stateless tools/call works.
- Privacy audit before commit: zero matches for personal names, `C:\Users`, `/Users/`,
  CV markers, secret patterns (`ghp_`, `sk-`, `xox*`, `AIza`, PEM/JWT blobs); all URLs are
  reserved placeholders (`auth.invalid`, `example.invalid`, `your-service.onrender.com`,
  `127.0.0.1`); all token strings are obviously fake test values.
- `deploy-wiki/` reviewed file-by-file — fully synthetic boilerplate, safe even public.
- `git add --dry-run` / staged-diff check confirmed exactly the intended 15 files; no
  `.venv`, `__pycache__`, or secret files staged.

## 5. Git history

```
92f7153 Add authenticated streamable-HTTP entry point for Render   (pushed)
7395ff8 Initial commit: read-only personal-wiki MCP server
```

Pushed to `origin/main` after explicit user approval. Working tree clean.

## 6. Remaining risks (noted, none blocking)

1. Repo visibility: content is synthetic/safe even if public, but keeping the repo
   private is still recommended.
2. `MCP_ALLOWED_HOSTS` unset at first deploy → Host-header validation off until set
   (bearer token still required; low impact). **Post-deploy step.**
3. `region: oregon` hardcoded in render.yaml — easy to change.
4. Free-tier cold start ~50 s after idle; with private snapshot enabled, each cold start
   re-downloads it (capped at 100 MiB).
5. Single shared bearer token = full read access for holders; rotate via Render env + restart.

## 7. Next steps (deployment, not yet done)

1. Keep or flip GitHub repo to private (recommended).
2. On Render: New → Blueprint → select repo (auto-detects `render.yaml`), plan Free.
3. Set secret `MCP_AUTH_TOKEN` (≥32 random chars, e.g. `openssl rand -hex 32`).
4. Deploy; verify `curl https://<service>/health` → `{"status":"ok"}`.
5. Set `MCP_ALLOWED_HOSTS=<service>.onrender.com` and redeploy.
6. Point an MCP client at `https://<service>.onrender.com/mcp` with the bearer token.
7. Optionally set `WIKI_SNAPSHOT_URL` (+ `WIKI_SNAPSHOT_SHA256`) to serve real content
   without committing it.

## 8. Quick local re-test

```bat
.venv\Scripts\python -m pytest -q
set WIKI_ROOT=.\deploy-wiki
set MCP_AUTH_TOKEN=<32+ random chars>
python remote_server.py
:: then: curl http://127.0.0.1:8000/health
```
