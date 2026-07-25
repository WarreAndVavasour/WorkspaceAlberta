# Deployment Guide

How to run the WorkspaceAlberta procurement server locally, in Docker, and in production.

## Environments at a Glance

| Mode | Entry point | Protocol | Use case |
|---|---|---|---|
| Local stdio | `python mcp-servers/canadabuys/server.py` | MCP over stdio | Claude Desktop, Cursor, OpenCode |
| Local HTTP | `python mcp-servers/canadabuys/server_http.py` | StreamableHTTP MCP + REST on :8000 | Development, REST testing |
| Docker | root `Dockerfile` → uvicorn on :8080 | Same as local HTTP | Any container host |
| Cloud Run (production) | container above | HTTPS | project `workspacealberta-prod` (org 63434412699), `https://workspacealberta-983058968342.northamerica-northeast1.run.app/mcp`, region `northamerica-northeast1` (Montréal), fronted by `elbowsupknivesout.warreandvavasour.com` (Cloudflare Worker `elbows-mcp`, cut over to this backend 2026-07-25) |
| Railway (alternative) | `railway.json` + `Procfile` | HTTPS | Dockerfile build, `/health` healthcheck |

## Environment Variables

| Variable | Required for | Notes |
|---|---|---|
| `CANADABUYS_DATA_DIR` | — | Cache dir; default `~/.canadabuys/` |
| `COHERE_API_KEY` | Cohere analysis, bid-room review | Primary direct route |
| `COHERE_PROD_API_KEY` | — | Failover on rate/quota/credit errors |
| `HF_TOKEN` (or `HUGGINGFACEHUB_API_TOKEN`) | HF fallback route | Token needs "Make calls to Inference Providers" permission |
| `E2B_API_KEY` | `process_bid_room` | Sandbox provisioning |
| `CANADABUYS_COHERE_MODEL` | — | Default `command-a-plus-05-2026` |
| `CANADABUYS_LOAD_ENV_FILE` | — | Set `0` to disable repo-local `.env` loading (recommended in production) |
| `ALBERTA_APC_API_BASE` / `ALBERTA_APC_APP_BASE` | — | APC endpoint overrides |
| `SUPABASE_URL` | Pro gate + multi-tenant storage | `https://<ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Pro gate + multi-tenant storage | Service-role secret; server-side only |
| `STRIPE_WEBHOOK_SECRET` | `/stripe/webhook` | Signing secret from the Stripe webhook endpoint |
| `STRIPE_SECRET_KEY` | Optional | Fallback key validator + mirroring issued keys into customer metadata |
| `WA_GATE_DISABLED` | — | Set `1` to disable Pro gating (dev). Gate also stays off if no validator is configured |

**Pro-tool gate:** when Supabase (or Stripe) validation is configured, the tools in `auth.PRO_TOOLS` (`process_bid_room`, `analyze_contract_with_cohere`, watchlist tools, `bid_no_bid_scorecard`) require `Authorization: Bearer wa_live_...` on both REST and `/mcp`. Free tools stay open. Subscribers get tenant-scoped profile/watchlist storage in the `wa_subscribers` table (migration: `pipelines/migrations/001_create_wa_subscribers.sql`). Provisioning flow: Stripe checkout → webhook issues a key (hash in Supabase, plaintext in `pending_key` and Stripe customer metadata) → email key to subscriber → cancellation webhook revokes within the 5-minute auth cache TTL. Verify a key with `GET /me`.

Local runs read a repo-root `.env` automatically (existing env vars win; secrets never printed). In hosted environments, inject secrets via the platform's secret manager and set `CANADABUYS_LOAD_ENV_FILE=0`.

## Local Development

```bash
python -m pip install -r requirements.txt
python -m pip install -r mcp-servers/canadabuys/requirements.txt

# stdio MCP (what desktop agents launch)
python mcp-servers/canadabuys/server.py

# hosted adapter with Swagger UI at http://localhost:8000/docs
uvicorn server_http:app --app-dir mcp-servers/canadabuys --host 0.0.0.0 --port 8000

# tests
python -m unittest tests.test_canadabuys_mcp_smoke
python -m unittest discover tests
```

MCP client config: see `.mcp.json` (points at production `/mcp`) and `mcp.json.example` for the stdio variant.

## Docker

```bash
docker build -t workspacealberta .
docker run -p 8080:8080 \
  -e COHERE_API_KEY=... -e E2B_API_KEY=... \
  -e CANADABUYS_LOAD_ENV_FILE=0 \
  workspacealberta
```

The image is `python:3.12-slim`, copies only `procurement_core/` and `mcp-servers/canadabuys/`, and serves uvicorn on 8080. Note: the CanadaBuys cache and `profile.json` live inside the container filesystem — mount a volume at the `CANADABUYS_DATA_DIR` path if you need persistence across restarts.

## Cloud Run (production)

Production lives in project `workspacealberta-prod` (service `workspacealberta`, region `northamerica-northeast1`). Deploys must run under an account with access to that project (currently `christian@warreandvavasour.com` via WSL gcloud):

```bash
gcloud run deploy workspacealberta \
  --source . \
  --region northamerica-northeast1 \
  --project workspacealberta-prod
```

Do not pass `--set-secrets` on redeploys: the new revision inherits the service's existing env/secret wiring. The service is public (`--allow-unauthenticated` already set); do not change ingress/auth settings.

> Migration note (2026-07-20, updated 2026-07-25): production previously ran in project `n8n-automation-project-459922` at `https://workspacealberta-719334491060.northamerica-northeast1.run.app`. The Cloudflare worker cutover below is done and verified, so that project is the **retired backend** — its service is still running and can now be deleted.

Montréal region keeps traffic on Canadian infrastructure, consistent with the project's sovereignty positioning. Cloud Run instances are ephemeral: the tender cache re-downloads on cold start (self-healing), but the saved business profile also resets — this is acceptable single-tenant, and is the main operational driver for the multi-user persistence work in `docs/tooling-roadmap.md`.

## Cloudflare cutover (done 2026-07-25)

The Cloudflare Worker `elbows-mcp` (which serves `elbowsupknivesout.warreandvavasour.com`) now rewrites every request to `https://workspacealberta-983058968342.northamerica-northeast1.run.app`. Verified after the flip: `/health` is byte-identical through the custom domain and the Cloud Run origin (25 tools, Pro gate enabled), and `tools/list` over `POST https://elbowsupknivesout.warreandvavasour.com/mcp` returns 25 tools.

The worker was dashboard-only; its source and `wrangler.jsonc` (custom-domain trigger, no bindings) now live in the Daily repo at `Projects/elbows-mcp/`. Redeploy it from there with `npx wrangler deploy`, not the dashboard editor, so the origin stays in version control.

Remaining step — delete the retired backend:

```bash
gcloud run services delete workspacealberta --project n8n-automation-project-459922 --region northamerica-northeast1
```

**Still HELD at the owner's request** (2026-07-25) even though the cutover is verified.

## Health & Smoke Checks

```bash
curl https://<host>/health          # {"status":"ok", "tools": 21, ...}
curl https://<host>/tools | head    # schema list
curl -X POST https://<host>/tools/summarize_contracts
```

`/health` never calls upstream sources, so it is safe for aggressive healthcheck intervals (Railway is configured at 30 s timeout).

## Operational Notes

- **CanadaBuys refresh:** the open CSV is a full snapshot; `refresh_data` (or the first unified call on an empty cache) re-downloads it. For a hosted service, schedule a refresh (cron/Cloud Scheduler hitting `POST /tools/refresh_data`) every few hours.
- **APC:** live-queried per request; failures degrade to warnings in tool output rather than errors.
- **Bid rooms:** each `process_bid_room` call provisions an E2B sandbox (default 900 s lifetime, killed after use). Cost scales with usage — cap concurrency on paid tiers.
- Further ops notes: `docs/deployment-ops/` (commercial licensing, Tailscale remote support) and `installer/systemd/` for on-prem installs.
