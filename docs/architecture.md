# WorkspaceAlberta Architecture

This document explains how the pieces fit together, from a tool call arriving over MCP down to the CanadaBuys CSV cache and the E2B sandbox.

## The One-Sentence Version

A single pure-Python procurement core (`procurement_core/`) does all the work; two thin adapters (`mcp-servers/canadabuys/server.py` for stdio, `server_http.py` for hosted StreamableHTTP MCP + REST) expose the identical tool surface to agents and APIs.

## Layer Diagram

```
┌────────────────────────────────────────────────────────────────┐
│  Clients                                                       │
│  Claude Desktop / Cursor / OpenCode (stdio MCP)                │
│  MCP-native agents over HTTP  ·  Any HTTP client (REST)        │
└───────────────┬───────────────────────────┬────────────────────┘
                │ stdio                     │ HTTPS
        ┌───────▼────────┐        ┌─────────▼──────────────┐
        │ server.py      │        │ server_http.py         │
        │ stdio adapter  │        │ FastAPI                │
        │                │        │  /mcp  StreamableHTTP  │
        │                │        │  /tools, /search, ...  │
        └───────┬────────┘        └─────────┬──────────────┘
                │      mcp_tools.py          │
                │  (shared tool schemas)     │
        ┌───────▼────────────────────────────▼──────────────┐
        │ procurement_core/service.py                       │
        │  call_tool_text(name, args) → markdown            │
        │  · CanadaBuys CSV client + cache                  │
        │  · Alberta APC JSON API client                    │
        │  · unified normalizer + deterministic scoring     │
        │  · business profile persistence                   │
        │  · Cohere routing (direct → prod key → HF router) │
        └───────┬──────────────────────────┬────────────────┘
                │                          │
   ┌────────────▼─────────────┐   ┌────────▼─────────────────────┐
   │ Data sources             │   │ procurement_core/            │
   │ · CanadaBuys open CSV    │   │   e2b_bid_room.py            │
   │ · APC purchasing.alberta │   │ E2B sandbox: download,       │
   │   .ca/api                │   │ extract, evidence tools,     │
   │ · ~/.canadabuys/ cache   │   │ in-sandbox Cohere review     │
   └──────────────────────────┘   └──────────────────────────────┘
```

## Key Design Decisions

**Adapters own zero logic.** Both servers import `get_mcp_tools()` (declared schemas) and `call_tool_text()` (dispatch). A tool behaves identically over stdio MCP, StreamableHTTP MCP, and REST, and is tested once. Adding a transport never means re-implementing a tool.

**Dispatch by name.** `service.TOOL_NAMES` is the canonical tool registry. `call_tool_text` resolves each name to a same-named async handler via `globals()`. Adding a tool is a three-file change: schema in `mcp_tools.py`, handler + `TOOL_NAMES` entry in `service.py`, test in `tests/`.

**Deterministic before generative.** Search, filtering, deadline ranking, profile matching, and the daily brief are plain Python — no model call, no per-request cost, reproducible output. The LLM (Cohere Command A+) is invoked only for judgment: tender fit review (`analyze_contract_with_cohere`) and the sandboxed bid-room analysis.

**Normalize early.** CanadaBuys rows (bilingual CSV headers like `title-titre-eng`) and APC responses (camelCase JSON) are converted into one shared opportunity shape (`source`, `reference`, `title`, `buyer`, `closing`, `region`, ...) so every unified tool works on one schema.

**Untrusted files never touch the service.** Tender attachments are downloaded, unzipped, and parsed inside a short-lived E2B sandbox (`e2b_bid_room.py`), with hard limits (5 attachments, 25 MB/file, 80k prompt chars, command timeouts). The Cohere review also runs inside the sandbox, with read-only evidence tools and a strict JSON response schema. Only a validated JSON artifact comes back.

**Model routing with failover.** `call_cohere_chat` tries `COHERE_API_KEY`, then `COHERE_PROD_API_KEY` on rate/quota/credit errors (`is_cohere_limit_error`), then falls back to the Hugging Face OpenAI-compatible router serving `CohereLabs/command-a-plus-05-2026-w4a4`. Status is inspectable without a model call via `check_cohere_status`.

## Data Flow Examples

**`search_opportunities` (unified search).** Load CanadaBuys cache (refresh once if empty) → filter rows by keyword/province/category → live `POST /api/opportunity/search` to APC → normalize both → sort by post date → render markdown listing with warnings for any degraded source.

**`daily_bid_brief`.** Market snapshot (federal cache count + APC total) → profile-scored matches within lookahead window → closing-soon list → suggested action. Sources degrade independently: if APC is down, the brief still ships with a warning line.

**`process_bid_room`.** Resolve reference (APC pattern `AB-YYYY-NNNNN` routes to the live APC detail API; anything else searches the CanadaBuys cache) → build payload (metadata + attachment URLs + profile) → boot E2B sandbox → inject and run the self-contained processor script → download/extract/evidence-bundle → in-sandbox Cohere structured review → JSON artifact back → validate → render markdown.

## Persistence

| Path | Contents |
|---|---|
| `~/.canadabuys/latest.csv` | Full CanadaBuys open-tender snapshot |
| `~/.canadabuys/latest.json` | Snapshot metadata (timestamp, row count) |
| `~/.canadabuys/profile.json` | Saved business profile (single-tenant today) |

Override the directory with `CANADABUYS_DATA_DIR`. The profile is per-deployment, not per-user — multi-user profile storage is the main prerequisite for hosted paid accounts (see `docs/authentication-and-multi-user-model.md` and `docs/tooling-roadmap.md`).

## Deployed Topology

Production endpoint: Google Cloud Run, `northamerica-northeast1` (Montréal) — Canadian region by design. `.mcp.json` points MCP clients at `https://workspacealberta-…run.app/mcp`. Railway config (`railway.json`, `Procfile`) and a `Dockerfile` exist for alternative hosting. See `docs/deployment.md`.

## Directory Map

| Path | Role |
|---|---|
| `procurement_core/` | All logic: `service.py` (tools + dispatch), `e2b_bid_room.py` (sandbox) |
| `mcp-servers/canadabuys/` | Adapters: `server.py` (stdio), `server_http.py` (hosted), `mcp_tools.py` (schemas), deploy files |
| `tests/` | Smoke + unit tests for the MCP server, HTTP app, and bid room |
| `docs/` | Specs, research, ops notes, this document |
| `pipelines/canadabuys/` | Data pipeline experiments |
| `packages/workspace-alberta-mcp/` | npm wrapper for `npx`-style install |
| `hermes/`, `installer/`, `scripts/` | Dashboard theming, systemd install, operational scripts |
