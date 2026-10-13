# Session Notes — End-to-End Local Demo Test (pre-Render)

**Date:** 2026-10-13
**Repo:** `personal-wiki-mcp`
**Outcome:** Complete — all checks PASS. No deploy performed.

---

## 1. Goal

Test the committed remote MCP implementation locally using **only** the synthetic demo wiki in `deploy-wiki/`, before any Render deployment.

Hard constraints honored throughout:
- No file modifications, commits, pushes, or deploys.
- Real personal wiki / CV never touched.
- Test token never printed, logged, or written to files.
- Existing Claude Desktop MCP configuration unchanged.
- Existing venv and dependencies used.
- On failure: report and stop; no auto-fixes.

## 2. Step 1 — Starting state verification

| Check | Result |
|---|---|
| Branch `main`, working tree clean | PASS |
| HEAD = `92f7153` (remote MCP commit) | PASS |
| `deploy-wiki/` synthetic-only (5 files) | PASS |
| `server.py` / `wiki_paths.py` unmodified | PASS |

`deploy-wiki/` contents:
```
deploy-wiki/_index.md
deploy-wiki/wikis.json
deploy-wiki/log.md
deploy-wiki/topics/sample/_index.md
deploy-wiki/topics/sample/articles/getting-started.md
```

## 3. Step 2 — Regression tests

```
.venv\Scripts\python.exe -m pytest -v
```

**Result: 93 passed, 0 failed, 0 skipped** (17.03s)

## 4. Step 3–4 — Live HTTP endpoint test

Server started as a subprocess with:
- `WIKI_ROOT` → absolute path to `deploy-wiki/`
- `MCP_AUTH_TOKEN` → runtime-generated ≥32-char token (never printed)
- `MCP_ALLOWED_HOSTS` → `127.0.0.1:<free-port>`
- `PORT` → free local port

### Check results

| # | Check | HTTP | Result |
|---|---|---|---|
| 1 | `GET /health` = exactly `{"status":"ok"}` | 200 | PASS |
| 2 | MCP without bearer token | 401 | PASS |
| 3 | MCP with wrong token | 401 | PASS |
| 4 | Authenticated `initialize` | 200 | PASS |
| 5 | `tools/list` = exactly 4 expected tools | 200 | PASS |
| 6 | All four `tools/call` | 200 each | PASS |
| 7 | `search_wiki("deployment sentinel")` → match found | 200 | PASS |
| 8 | `read_article` returns synthetic demo article | 200 | PASS |
| 9 | Path traversal attempts rejected; no outside disclosure | — | PASS |
| 10 | No token / personal path / secret in responses or logs | — | PASS |

### Four tools confirmed

- `list_wikis`
- `get_wiki_index`
- `search_wiki`
- `read_article`

### Tool result highlights

- **list_wikis:** 2 wikis — `hub` and `sample` (both synthetic)
- **search_wiki("deployment sentinel"):** 1 match at `topics/sample/articles/getting-started.md:16`
- **read_article:** full synthetic Getting Started article returned
- **Traversal:** `../server.py`, `..\\server.py`, `topics/../../server.py`, `C:\Windows\win.ini`, `/etc/passwd` all rejected

## 5. Step 5 — Cleanup

- Server terminated in `finally` block; no `remote_server.py` process left running.
- Token never written to disk.
- Temp test script and log removed.
- Project tree unchanged.

## 6. Notes

- Pre-existing `server.py` (stdio) processes from earlier sessions were observed; not started by this test.
- Untracked `SESSION-2026-10-13-render-remote-mcp.md` appeared in repo root (session-capture hook); not created/modified by this test.

**Overall: ALL CHECKS PASS. Not deployed to Render.**
