---
title: Getting Started
summary: How the sample wiki proves the remote MCP endpoint works end to end.
tags: [sample, deployment, mcp]
created: 2026-10-13
updated: 2026-10-13
confidence: high
---

# Getting Started

This article exists so the deployment is verifiable end to end:

1. `list_wikis` should report the `hub` and `sample` wikis.
2. `get_wiki_index` with wiki `sample` returns the index you are reading from.
3. `search_wiki` for the phrase "deployment sentinel" finds this file
   (that exact phrase is the sentinel used by smoke tests).
4. `read_article` with path `topics/sample/articles/getting-started.md`
   returns this text.

None of this content is personal. Replace the whole `deploy-wiki/` tree
with a privately fetched snapshot to serve real content — see
`DEPLOYMENT.md` for the private-snapshot fetch option.
