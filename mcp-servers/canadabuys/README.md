# Procurement MCP Server

This server powers the procurement MCP wiring in this repository.

It exposes CanadaBuys and Alberta Purchasing Connection procurement data over MCP so an assistant can help a business search opportunities, review details, and triage what to pursue.

## Run Directly

From the repo root:

```bash
python mcp-servers/canadabuys/server.py
```

## Available Tools

Primary unified tools:

- `search_opportunities`
- `get_opportunity_details`
- `list_deadlines`
- `find_matching_opportunities`
- `daily_bid_brief`

Source-specific tools:

- `set_business_profile`
- `find_opportunities`
- `get_my_profile`
- `search_contracts`
- `get_contract_details`
- `list_upcoming_deadlines`
- `summarize_contracts`
- `refresh_data`
- `search_alberta_opportunities`
- `get_alberta_opportunity_details`
- `list_alberta_deadlines`
- `summarize_alberta_opportunities`
- `find_alberta_opportunities`
- `check_cohere_status`
- `analyze_contract_with_cohere`

`daily_bid_brief` is intentionally free/local. It is meant to build the habit of checking new work before any pricing or community layer exists.

## Configuration

No environment variables are required for local use.

Optional:

- `CANADABUYS_DATA_DIR`: override the default cache directory
- `ALBERTA_APC_API_BASE`: override the Alberta Purchasing Connection API base, currently `https://purchasing.alberta.ca/api`
- `ALBERTA_APC_APP_BASE`: override the Alberta Purchasing Connection app base, currently `https://purchasing.alberta.ca`
- `COHERE_API_KEY` or `COHERE_PROD_API_KEY`: enable Cohere Command A+ analysis through Cohere's API
- `HF_TOKEN` or `HUGGINGFACEHUB_API_TOKEN`: fallback route for Cohere Command A+ analysis through Hugging Face Inference Providers
- `CANADABUYS_COHERE_MODEL`: override the default Cohere model, currently `command-a-plus-05-2026`
- `CANADABUYS_COHERE_HF_MODEL`: override the default HF model route, currently `CohereLabs/command-a-plus-05-2026-w4a4:cohere`
- `CANADABUYS_COHERE_CHAT_COMPLETIONS_URL`: override the Cohere chat completions endpoint
- `CANADABUYS_HF_CHAT_COMPLETIONS_URL`: override the Hugging Face chat completions endpoint

When both Cohere keys are set, the server uses `COHERE_API_KEY` first and retries once with `COHERE_PROD_API_KEY` only for rate-limit, quota, or credit-style failures.

By default the server caches under `~/.canadabuys` and loads a repo-root `.env` file for local runs when one exists.

## Smoke Test

From the repo root:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

## Data Source

- CanadaBuys open tender notices
- `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`
- Alberta Purchasing Connection public opportunity API
- `https://purchasing.alberta.ca/api/opportunity/search`
