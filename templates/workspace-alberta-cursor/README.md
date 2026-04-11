# Workspace Alberta — Cursor template

Copy `.cursor/mcp.json` from this folder into the root of a project that already contains `mcp-servers/canadabuys/`, or open the **WorkspaceAlberta** repository itself (this file matches the repo layout).

## First run

1. Python 3.10+ on your PATH as `python`.
2. From the workspace root: `pip install -r mcp-servers/canadabuys/requirements.txt`
3. Restart MCP in Cursor if the server does not connect.

By default the server caches under `~/.canadabuys`. To use a project-local cache, set `CANADABUYS_DATA_DIR` in the MCP `env` block (absolute path recommended).

## Managed server (hardware bundle)

When you ship a hosted Build Canada MCP (SSE/HTTP), generate config with:

`python generator/generator.py buildcanada_mcp_remote`

Set `BUILD_CANADA_MCP_URL` in your environment to the base URL Cursor should call.
