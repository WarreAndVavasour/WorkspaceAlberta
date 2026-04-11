# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project Overview

WorkspaceAlberta is a bare-bones Cursor and OpenCode template with a single MCP server built in: CanadaBuys.

This repo is intentionally narrow:

- one procurement-focused MCP server
- one Cursor config
- one OpenCode config
- one smoke test

Do not treat this repo as a workspace generator. There are no profiles, tool catalogs, or customer-specific workspace builders anymore.

## Key Commands

Install the minimal local dependency:

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

## Architecture

### Root Template

- [`.cursor/mcp.json`](.cursor/mcp.json): Cursor MCP config using the server id `buildcanada`
- [`opencode.json`](opencode.json): OpenCode project config for the same local server
- [`README.md`](README.md): the canonical setup and usage doc

### MCP Server

- [`mcp-servers/canadabuys/server.py`](mcp-servers/canadabuys/server.py): stdio MCP server
- [`mcp-servers/canadabuys/server_sse.py`](mcp-servers/canadabuys/server_sse.py): SSE/HTTP transport variant

### Tests

- [`tests/test_canadabuys_mcp_smoke.py`](tests/test_canadabuys_mcp_smoke.py): verifies the stdio server starts and answers a tool call

## Working Rules

- Keep the root template minimal.
- Do not reintroduce profile generation, tool catalogs, or workspace scaffolding.
- Do not assume any business integration exists beyond the CanadaBuys MCP unless it has been deliberately added.
- If future tooling is explored, keep it out of the root template until it is proven.

## Communication

- Use direct, plain language.
- Focus on the procurement problem the user is trying to solve.
- Explain MCP as a practical connection layer, not as abstract infrastructure.
- Confirm before making changes to external services.
