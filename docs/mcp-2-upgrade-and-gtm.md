# MCP 2.0 Upgrade, Product Leverage, and Go-to-Market

Status: **migration complete and verified locally** (2026-08). This doc records
what changed, what MCP 2.0 unlocks for the product, and how to take it to the
shops that make Canadian industry work.

## 1. What we moved to 2.0

The procurement server (CanadaBuys + Alberta Purchasing Connection) and the
OPERA analytics server both upgraded from `mcp` 1.x to `mcp>=2,<3`, which
implements the **2026-07-28 revision** of MCP *and* still serves every 2025-era
client unchanged. One server now speaks both eras at once — no fork, no
separate deployment, no stranded desktop agents.

What actually changed in code:

- **`mcp>=2,<3`** in `requirements.txt` and `mcp-servers/canadabuys/requirements.txt`
  (plus `sse-starlette>=3.0.0`).
- **Low-level `Server` handlers** moved from `@server.list_tools()` /
  `@server.call_tool()` decorators to constructor params
  (`Server(name, on_list_tools=..., on_call_tool=...)`) with `(ctx, params)`
  signatures and full result types (`ListToolsResult`, `CallToolResult`).
- **`Tool.inputSchema` → `input_schema`** (snake_case) across both tool
  catalogs; `serialize_tool()` now emits wire-case keys via
  `model_dump(by_alias=True)` so the REST `/tools` payload is unchanged for
  callers.
- **Auth header** now read from the handler context (`ctx.request.headers`)
  instead of the removed `server.request_context` ContextVar.
- **Tool errors** are returned as `CallToolResult(is_error=True, ...)` so the
  model still reads them (v2 no longer auto-wraps raised exceptions).

Verified: `test_canadabuys_mcp_smoke`, `test_procurement_http_app`, and
`test_opera_analytics_smoke` all pass on `mcp 2.0.0` (stdio round-trip, raw
JSON-RPC `initialize` + `tools/list` over StreamableHTTP, discovery endpoints,
and the `/tools` schema).

## 2. What 2.0 unlocks for the product

The protocol change that matters most is that **a 2026-era client opens no
session** — each request is self-contained. For a public, multi-tenant,
Cloud Run-hosted service, that removes the last reason to pin a request to a
worker. But the product opportunities are the new capabilities, in rough
priority order for a bid-workflow tool:

### 2.1 Elicitation / `Resolve(fn)` — turn search into a guided bid room

Today a shop describes itself by calling `set_business_profile` or passing an
inline `profile`. MCP 2.0's `Resolve(...)` lets a tool **ask the user a question
mid-call and get the answer back**, portably across both old and new clients
(live elicitation on legacy sessions, multi-round-trip on 2026).

Product shape: a `qualify_opportunity` / `bid_no_bid` flow that walks the owner
through the questions a bid desk actually asks — bonding capacity, region,
trades, deadline runway, incumbent relationship — and scores each answer into
the existing `bid_no_bid_scorecard`. The model stops being a search box and
becomes a working session.

### 2.2 Subscriptions (`subscriptions/listen`) — push, don't poll

The daily bid brief and watchlist are pull-based today. MCP 2.0's
`subscriptions/listen` gives the server a one-way notify channel:
`notify_tools_changed()`, resource updates, and custom events. A subscribed
client gets **"three new Alberta tenders match your steel profile"** or **"a
watched solicitation got an amendment"** pushed to it, instead of the shop
remembering to ask. This is the single biggest "it does the work for you" move.

### 2.3 Structured output + cache hints — feed the other systems

- `structured_content` lets a tool return typed JSON alongside the markdown, so
  a tender, a match, or a scorecard can be consumed by a shop's CRM/ERP/spreadsheet
  without parsing prose. This is what makes WorkspaceAlberta **the tool between
  systems**, not a silo.
- Cache hints (`ttlMs` / `cacheScope`) let clients cache tender lists the way the
  server already caches CanadaBuys, cutting repeat traffic on the shared endpoint.

### 2.4 Header-based routing (`Mcp-Method` / `Mcp-Param-*`) — a cheaper gate

Modern requests carry method/param headers, so a gateway or rate limiter can
route/limit on headers alone. This is a direct fit for the Pro-tool gate: the
expensive tools (`process_bid_room`, `analyze_contract_with_cohere`) can be
metered at the edge before they ever hit a sandbox or a model call.

### 2.5 Observability and extensions

- OpenTelemetry ships on by default, so the hosted endpoint gets end-to-end
  tracing for free.
- Extensions (SEP-2133) give a namespaced way to bundle the bid-room or
  watchlist as a first-class capability later, without expanding the core tool
  list.

## 3. Distribution: be the layer between the systems and the work

Positioning: WorkspaceAlberta is not a search tool. It is the connective tissue
between the public tender systems a shop must already read (CanadaBuys, Alberta
APC, and next: municipal and provincial portals) and the systems a shop uses to
actually bid and deliver (its CRM, ERP, estimating spreadsheets, project
trackers). "Getting work done" means: discover → qualify → decide → bid →
track — with the agent and the MCP server carrying the data across each hop.

### 3.1 Channels that already exist — finish them

- **MCP registries.** The repo already ships `server.json`, `/.well-known/mcp.json`,
  an A2A agent card, and an npm bridge (`@warreandvavasour/workspace-alberta`).
  Publish the hosted endpoint to the MCP registries the target buyers browse
  (Claude's MCP directory, Cursor/VS Code marketplaces, OpenCode, and the
  community registries). A registry listing is a zero-friction install for a shop
  that already runs one of these agents.
- **One-command client configs.** `.mcp.json` and `mcp.json.example` already give
  the `"type": "http", "url": "…/mcp"` block; the npm package covers stdio-only
  clients. Package these as copy-paste blocks per client on the landing page.

### 3.2 The on-prem angle for industrial shops

Industrial shops are often on a shop floor with spotty cloud trust and legacy
machines. The repo already contains a Pi/terminal installer
(`installer/systemd`, `docs/deployment-ops/pi-out-of-box-setup.md`). Offer a
**"shop box"** — a Raspberry Pi or mini box that runs an agent + the local stdio
server + a screen showing the daily brief — so a fabricator gets the same
product with no cloud account and no IT department. The hosted endpoint stays
the shared/multi-tenant path; the box is the single-tenant, on-site path.

### 3.3 Freemium is already wired — make it the funnel

- **Free:** search, deadlines, daily brief, match ranking (already open, no key).
- **Pro ($85 CAD/month, Stripe already wired):** bid-room E2B processing,
  Cohere tender analysis, watchlist, scorecard.

The daily brief is deliberately free as a habit builder. Distribution = get a
shop's daily brief in front of them every morning, then the paid tools are the
natural "now let's actually chase this one" step.

### 3.4 Go to market through the industry, not the tech press

- **Industry associations & guilds:** Alberta's industrial construction and
  steel/fabrication associations, Canadian Manufacturers & Exporters, and
  provincial fabrication/welding bodies. A co-branded "find the work" channel
  for members is the highest-leverage single move.
- **Show, don't tell:** a 60-second demo that starts from "what does your shop
  do?" and ends with a ranked list of live Alberta + federal tenders and a
  bid/no-bid call on the top one. That's the whole pitch; it runs on the free
  tier.

## 4. Suggested next steps

1. Deploy the 2.0 build to Cloud Run (run the CI smoke first; the live URL stays
   unchanged).
2. Ship the first `Resolve`-backed tool (`qualify_opportunity`) behind the free
   tier, using `bid_no_bid_scorecard` as the scoring core.
3. Add structured output to `search_opportunities` / `find_matching_opportunities`
   so the results drop into a shop's own systems.
4. Add `subscriptions/listen` support for "new matches" and "amendment" pushes.
5. Publish to MCP registries and draft the one-page association pitch.
