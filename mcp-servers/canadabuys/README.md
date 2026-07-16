# Procurement MCP Server

This server powers the procurement MCP wiring in this repository.

It exposes CanadaBuys and Alberta Purchasing Connection procurement data over MCP so an assistant can help a business search opportunities, review details, and triage what to pursue.

The server is now split into:

- `procurement_core/service.py`: pure Python procurement logic shared by every adapter
- `server.py`: local stdio MCP adapter for MCP-first desktop/agent tools
- `server_http.py`: hosted StreamableHTTP MCP plus REST/OpenAPI adapter for deployed use

## Run Directly

From the repo root:

```bash
python mcp-servers/canadabuys/server.py
```

## Hosted Endpoint

From the repo root:

```bash
uvicorn server_http:app --app-dir mcp-servers/canadabuys --host 0.0.0.0 --port 8000
```

Hosted routes:

- `GET/POST/DELETE /mcp`: modern StreamableHTTP MCP endpoint (stateless, JSON responses; no session bookkeeping required and clients that send only `Accept: application/json` are accepted)
- `GET /`: human-friendly landing page with connect instructions
- `GET /health`: health check
- `GET /tools`: MCP tool schemas as JSON
- `POST /tools/{tool_name}`: call any MCP tool over HTTP
- `POST /search`: unified CanadaBuys + Alberta APC search
- `GET /details/{reference}`: opportunity details
- `POST /deadlines`: closing-soon opportunities
- `POST /matches`: profile-ranked opportunities
- `POST /brief`: daily bid brief
- `GET /docs`: Swagger UI
- `GET /openapi.json`: OpenAPI schema for non-MCP AI tools

Docker build from the repo root:

```bash
docker build -f mcp-servers/canadabuys/Dockerfile -t workspacealberta-procurement .
docker run --env-file .env -p 8080:8080 workspacealberta-procurement
```

Production note: the profile store is file-backed under `CANADABUYS_DATA_DIR`, shared by every caller. For public multi-user deployments set `WORKSPACEALBERTA_PUBLIC_MODE=1`: the shared-file profile tools (`set_business_profile`, `get_my_profile`) are hidden and blocked, and callers pass an inline `profile` argument (company_name, location, description, optional capabilities/industries) to `find_matching_opportunities`, `daily_bid_brief`, `find_opportunities`, and `find_alberta_opportunities` instead. CORS is enabled so browser-based MCP clients can connect. See `docs/deployment-ops/public-endpoint-accessibility.md` for the full operator checklist.

## Connect an MCP Client

Use the deployed StreamableHTTP endpoint:

```text
https://<host>/mcp
```

Local test endpoint:

```text
http://127.0.0.1:8000/mcp
```

For Hermes native MCP:

```yaml
mcp_servers:
  workspacealberta:
    url: "https://<host>/mcp"
    timeout: 180
    connect_timeout: 60
```

For MCP clients that only support local command/stdio servers, use the npm bridge package after it is published:

```json
{
  "mcpServers": {
    "workspacealberta": {
      "command": "npx",
      "args": ["-y", "@warreandvavasour/workspace-alberta"]
    }
  }
}
```

The npm package does not run the procurement server locally. It bridges stdio clients to the hosted StreamableHTTP endpoint.

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

- `WORKSPACEALBERTA_PUBLIC_MODE`: set to `1` on shared public deployments to hide the shared-file profile tools and require inline `profile` arguments
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
python -m unittest tests.test_procurement_http_app
```

## Data Source

- CanadaBuys open tender notices
- `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`
- Alberta Purchasing Connection public opportunity API
- `https://purchasing.alberta.ca/api/opportunity/search`
