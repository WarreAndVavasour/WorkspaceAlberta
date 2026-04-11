# CanadaBuys MCP Server

This server powers the root Cursor and OpenCode configs in this repository.

It exposes CanadaBuys procurement data over MCP so an assistant can help a business search opportunities, review details, and triage what to pursue.

## Run Directly

From the repo root:

```bash
python mcp-servers/canadabuys/server.py
```

## Available Tools

- `set_business_profile`
- `find_opportunities`
- `get_my_profile`
- `search_contracts`
- `get_contract_details`
- `list_upcoming_deadlines`
- `summarize_contracts`
- `refresh_data`

## Configuration

No environment variables are required for local use.

Optional:

- `CANADABUYS_DATA_DIR`: override the default cache directory

By default the server caches under `~/.canadabuys`.

## Smoke Test

From the repo root:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

## Data Source

- CanadaBuys open tender notices
- `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`
