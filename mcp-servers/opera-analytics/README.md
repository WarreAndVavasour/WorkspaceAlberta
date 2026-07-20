# OPERA Analytics MCP Server

A read-only analytics data tap for Oracle OPERA Cloud Reporting & Analytics (R&A) Data APIs.

Wouldn't it be great if a hotel could ask its own assistant for last month's occupancy or tomorrow's arrivals, and get the answer straight from its own OPERA Cloud data — as itself, with its own credentials, without exporting anything by hand? That is what this server does. It signs into OPERA Cloud with the hotel's own OAuth2 credentials (password grant), runs safe read-only GraphQL queries against the R&A subject areas, and can save the rows to local CSV files or synced tables for offline analysis.

The server is split into:

- `opera_core/service.py`: pure Python tool logic shared by every adapter
- `opera_core/catalog.py` + `opera_core/schemas/`: metadata for 75 bundled OPERA subject-area schemas, used to validate queries before they run
- `opera_core/store.py`: local CSV exports and synced tables for offline analysis
- `server.py`: local stdio MCP adapter for MCP-first desktop/agent tools

All tools are read-only. Nothing here writes back to OPERA.

## Tools

- `opera_auth_status`: check configuration, mock mode, and whether an OAuth token can be obtained. Never displays secrets.
- `list_subject_areas`: list the available R&A subject areas (Financial, Statistics, Rates, Profiles, Bookings, and more) grouped by category.
- `describe_subject_area`: show the fields, filter inputs, and an example GraphQL query for one subject area.
- `run_graphql_query`: run a raw read-only GraphQL query against OPERA R&A.
- `query_subject_area`: run a catalog-validated query — unknown fields are rejected with the valid list, and the generated GraphQL is shown.
- `export_to_csv`: query a subject area and save the rows to a local CSV file.
- `sync_subject_area`: query a subject area and sync the rows into a local table.
- `list_local_tables`: list local tables created by `sync_subject_area`, with row counts.
- `query_local_data`: run read-only SQL against local synced tables.

## Getting Credentials

Credentials come from the hotel's own OPERA Cloud Developer Portal. The hotel (or its integration partner) registers an application there, which issues the `client_id`, `client_secret`, and `app_key` for the hotel's environment, and the hotel user authenticates as themselves with their own OPERA username and password. The base URL is the OPERA Cloud R&A endpoint for the hotel's region and tenancy.

These credentials belong to the hotel. They are read from the environment, never logged, and never echoed into tool output.

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPERA_BASE_URL` | live mode | OPERA Cloud R&A base URL for the hotel's tenancy |
| `OPERA_APP_KEY` | live mode | Application key from the Developer Portal |
| `OPERA_CLIENT_ID` | live mode | OAuth2 client ID from the Developer Portal |
| `OPERA_CLIENT_SECRET` | live mode | OAuth2 client secret from the Developer Portal |
| `OPERA_HOTEL_ID` | live mode | Hotel/resort code the queries run against |
| `OPERA_USERNAME` | live mode | The hotel user's OPERA username |
| `OPERA_PASSWORD` | live mode | The hotel user's OPERA password |
| `OPERA_GRANT_TYPE` | no | OAuth2 grant type (default `password`) |
| `OPERA_MOCK` | no | Set to `1` to run offline against demo data — no credentials needed |
| `OPERA_DATA_DIR` | no | Directory for CSV exports and synced tables (default: `.opera_data` under the repo root) |

## Mock Mode

Set `OPERA_MOCK=1` and every tool works fully offline against demo data — no base URL, no credentials. This is the way to try the tool surface, the catalog, and the local CSV/table pipeline before wiring up real credentials.

## Run Directly

From the repo root:

```bash
python mcp-servers/opera-analytics/server.py
```

Run the tests:

```bash
python -m unittest tests.test_opera_analytics_smoke
python -m unittest tests.test_opera_catalog tests.test_opera_client tests.test_opera_store tests.test_opera_service
```

## Connect an MCP Client

For MCP clients that launch a local stdio server:

```json
{
  "mcpServers": {
    "opera-analytics": {
      "command": "python",
      "args": ["mcp-servers/opera-analytics/server.py"],
      "cwd": "<path-to-repo>",
      "env": {
        "OPERA_BASE_URL": "https://<your-opera-cloud-host>",
        "OPERA_APP_KEY": "<your-app-key>",
        "OPERA_CLIENT_ID": "<your-client-id>",
        "OPERA_CLIENT_SECRET": "<your-client-secret>",
        "OPERA_HOTEL_ID": "<your-hotel-code>",
        "OPERA_USERNAME": "<your-opera-username>",
        "OPERA_PASSWORD": "<your-opera-password>"
      }
    }
  }
}
```

Or set `"OPERA_MOCK": "1"` in `env` to try it with no credentials at all.
