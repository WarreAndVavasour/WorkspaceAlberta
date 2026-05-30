---
name: gbrain
description: Use GBrain by Garry Tan as the repo-local memory/indexing layer for WorkspaceAlberta research, docs, and agent context.
version: 1.0.0
author: WorkspaceAlberta
license: MIT
metadata:
  source_id: workspacealberta
  gbrain_repo: https://github.com/garrytan/gbrain
  wrapper: /home/chris/.local/bin/gbrain
---

# GBrain for WorkspaceAlberta

Use this skill when an agent working in this repository needs to search, query, sync, or understand the WorkspaceAlberta knowledge context through GBrain.

GBrain is Garry Tan's open-source personal knowledge brain: a local-first TypeScript CLI and MCP server that stores a searchable brain in `~/.gbrain`, supports hybrid keyword/vector retrieval, and can sync git repositories as recurring sources.

## Local setup

- GBrain wrapper: `/home/chris/.local/bin/gbrain`
- Local GBrain checkout: `/home/chris/gbrain`
- Brain repository: `/home/chris/brain`
- Brain database: `/home/chris/.gbrain/brain.pglite`
- WorkspaceAlberta source id: `workspacealberta`
- WorkspaceAlberta path: `/mnt/c/Users/chris/WorkspaceAlberta`
- Source marker: `.gbrain-source`

Use the explicit wrapper path. Do not rely on `PATH`, because other shells may resolve a different `gbrain` binary.

## Common commands

From anywhere:

```bash
GB=/home/chris/.local/bin/gbrain
REPO=/mnt/c/Users/chris/WorkspaceAlberta
"$GB" sources list
"$GB" sync --source workspacealberta --no-pull --yes --no-embed
"$GB" search "WorkspaceAlberta"
"$GB" query "what does this repo say about CanadaBuys and MCP?" --no-expand
# Optional, when embedding quota is available:
"$GB" embed --stale
```

From the repo root:

```bash
GB=/home/chris/.local/bin/gbrain
"$GB" sync --source workspacealberta --no-pull --yes --no-embed
"$GB" search "Wouldn't it be great if"
# Optional, when embedding quota is available:
"$GB" embed --stale
```

## How to use it here

1. Treat GBrain as a lookup and indexing layer for repository context.
2. Use it to retrieve prior research, specs, and cross-file context before broad edits.
3. Keep CanadaBuys as the primary working integration for procurement tasks.
4. Do not use GBrain as a replacement for the repository's canonical tests, source files, or MCP server behavior.
5. After changing repo docs or agent setup, sync the source and verify with a known phrase search.

## Verification checklist

After installation or meaningful repo documentation changes:

```bash
GB=/home/chris/.local/bin/gbrain
cd /mnt/c/Users/chris/WorkspaceAlberta
"$GB" sources list
"$GB" sync --source workspacealberta --no-pull --yes --no-embed
"$GB" search "CanadaBuys MCP server"
# Optional, when embedding quota is available:
"$GB" embed --stale
python -m unittest tests.test_canadabuys_mcp_smoke
```

Expected signs of success:

- `sources list` includes `workspacealberta` with nonzero pages.
- Search returns visible WorkspaceAlberta files such as `README.md` or `AGENTS.md`.
- The CanadaBuys MCP smoke test passes.

## Guardrails

- Do not publish private local brain contents.
- Do not commit generated brain databases or local GBrain state.
- Hidden skill directories may not be indexed by GBrain source sync. Verify this file directly, then verify GBrain ingest using visible files like `AGENTS.md` and `README.md`.
- If OpenAI embedding quota is exhausted, use `sync --no-embed` and keyword `search` for verification. Run `embed --stale` later when quota is available to enable vector/hybrid quality.
- Confirm before changing external services, remote MCP deployments, or hosted GBrain HTTP/OAuth configuration.
