# WorkspaceAlberta

Bare-bones Cursor and OpenCode workspace template with the CanadaBuys MCP prewired.

This repo is the MVP.

- One MCP server.
- One Cursor config.
- One OpenCode config.
- No profile generator.
- No tool catalog.
- No workspace scaffolder.

## What You Get

- `.cursor/mcp.json` wired to the local CanadaBuys server
- `opencode.json` wired to the same server for OpenCode
- `mcp-servers/canadabuys/server.py` as the MCP entrypoint
- `tests/test_canadabuys_mcp_smoke.py` to prove the server starts and responds

## Setup

1. Install Python 3.10+ and make sure `python` is on your `PATH`.
2. From the repo root, run:

```bash
python -m pip install -r requirements.txt
```

3. Open the repo root in Cursor or OpenCode.
4. In Cursor, restart MCP if `buildcanada` does not connect on first open.
5. Start asking procurement questions.

## Example Prompts

- "Set my business profile: Edmonton steel fabricator serving commercial construction."
- "Find federal opportunities that match my business profile."
- "Show opportunities closing in the next 14 days."
- "Get details on reference number WSXXXXXX."
- "Summarize current federal opportunities for fencing or metal fabrication."

## Smoke Test

Run:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

The smoke test proves:

- the MCP server starts over stdio
- MCP initialization succeeds
- the expected procurement tools are exposed
- a tool call returns text

## Notes

- Local setup does not require any environment variables.
- By default, the server caches data under `~/.canadabuys`.
- Set `CANADABUYS_DATA_DIR` if you want an isolated cache directory.

## What This Repo Is Not

- Not a workspace generator
- Not a catalog of SMB tools
- Not a profile builder
- Not a managed hosting layer

Custom tools can be added later, but this repo starts with one job: give Cursor and OpenCode a working CanadaBuys MCP out of the box.
