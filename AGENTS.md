# AGENTS.md

This file provides guidance to Codex and Codex-like agents working in this repository.

## Project Overview

WorkspaceAlberta is a Codex/OpenClaw-first procurement workspace.

The repo is intentionally narrow:

- one CanadaBuys MCP server
- one Cursor workspace config
- one OpenCode project config
- one smoke test for the MCP server

This is not a workspace generator, profile builder, or catalog of business tools.

## Agent Priorities

1. Keep the root template minimal.
2. Preserve the brand voice and "Wouldn't it be great if..." ethos in user-facing copy.
3. Treat CanadaBuys as the primary working integration.
4. Prefer small, verifiable changes over broad framework expansion.
5. Run the MCP smoke test after changes that affect the server, config, or agent setup.

## Codex / OpenAI Instructions

Always use the OpenAI developer documentation MCP server if you need to work with the OpenAI API, ChatGPT Apps SDK, Codex, models, MCP wiring, or tool configuration without me having to explicitly ask.

If you are changing OpenAI- or Codex-related setup in this repo:

- consult the `openaiDeveloperDocs` MCP server first
- prefer official OpenAI guidance over memory
- keep OpenAI-specific setup separate from the Build Canada MCP logic

## Primary Repo Surfaces

- [README.md](C:\Users\chris\WorkspaceAlberta\README.md): brand narrative and user-facing overview
- [.cursor/mcp.json](C:\Users\chris\WorkspaceAlberta\.cursor\mcp.json): Cursor MCP config
- [opencode.json](C:\Users\chris\WorkspaceAlberta\opencode.json): OpenCode project config
- [mcp-servers/canadabuys/server.py](C:\Users\chris\WorkspaceAlberta\mcp-servers\canadabuys\server.py): stdio MCP server
- [tests/test_canadabuys_mcp_smoke.py](C:\Users\chris\WorkspaceAlberta\tests\test_canadabuys_mcp_smoke.py): startup and response smoke test
- [mcp-servers/opera-analytics/server.py](C:\Users\chris\WorkspaceAlberta\mcp-servers\opera-analytics\server.py): OPERA Cloud analytics stdio MCP server
- [tests/test_opera_analytics_smoke.py](C:\Users\chris\WorkspaceAlberta\tests\test_opera_analytics_smoke.py): OPERA analytics startup and response smoke test

## Key Commands

Install the minimal dependency:

```bash
python -m pip install -r requirements.txt
```

Run the MCP server directly:

```bash
python mcp-servers/canadabuys/server.py
```

Run the smoke test:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

## Build Canada MCP Guidance

Use the Build Canada tools for:

- searching federal procurement opportunities
- inspecting tender details
- reviewing upcoming deadlines
- matching opportunities to a saved business profile

Do not assume the repo has CRM, ERP, spreadsheet, or accounting integrations unless they are explicitly added later.

## GBrain Knowledge Layer

GBrain by Garry Tan is available as a repo-local lookup/indexing layer, not a replacement for the CanadaBuys MCP server or canonical tests.

- Repo source id: `workspacealberta`
- Preferred wrapper: `/home/chris/.local/bin/gbrain`
- Source marker: `.gbrain-source`
- Repo-local skill: `.claude/skills/gbrain/SKILL.md`

Common commands:

```bash
GB=/home/chris/.local/bin/gbrain
"$GB" sources list
"$GB" sync --source workspacealberta --no-pull --yes --no-embed
"$GB" search "CanadaBuys MCP server"
"$GB" query "what does this repo say about CanadaBuys and MCP?" --no-expand
# Optional, when embedding quota is available:
"$GB" embed --stale
```

After changing visible repo docs or agent setup, sync the source and verify with a known phrase search.

## Editing Rules

- Keep the repo Codex/OpenClaw-specific.
- Do not reintroduce Claude-specific repo guidance files.
- Do not reintroduce generator, profile, or catalog workflows.
- Keep README changes surgical unless the user explicitly asks for a rewrite.
- When adding OpenCode config, prefer project-level configuration in `opencode.json`.
- When adding Codex guidance, prefer `AGENTS.md` over scattered duplicate instruction files.

## Communication

- Be direct.
- Use plain language.
- Preserve the tone of the existing brand copy.
- Explain MCP as a practical connection layer, not abstract infrastructure.
- Confirm before making changes to external services.
