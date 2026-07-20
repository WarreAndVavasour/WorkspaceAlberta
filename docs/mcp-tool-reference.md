# MCP Tool & REST API Reference

Every tool exposed by the WorkspaceAlberta procurement server, with arguments, behaviour, data sources, and failure modes. All tools return markdown text. The same tools are callable three ways:

- **stdio MCP** — `python mcp-servers/canadabuys/server.py`
- **StreamableHTTP MCP** — `POST /mcp` on the hosted endpoint
- **REST** — `POST /tools/{tool_name}` with a JSON arguments body, or the named convenience routes listed at the end

Arguments are all optional unless marked **required**. Integer arguments are clamped server-side to the documented ranges.

---

## Unified Tools (primary surface)

### `search_opportunities`
Search CanadaBuys and Alberta Purchasing Connection together.

| Arg | Type | Default | Notes |
|---|---|---|---|
| `keywords` | string | — | Matched against title, buyer, category, region, description, reference |
| `source` | string | `all` | `all`, `federal` (aliases: canadabuys, canada, national), `alberta` (alias: apc) |
| `province` | string | — | Region filter; a non-Alberta province skips the APC source with a warning |
| `category` | string | — | Free text for federal; mapped to APC codes (services→SRV, goods→GD, construction→CNST) for Alberta |
| `limit` | int | 20 | 1–50, combined across sources |

Results sort newest-posted first. Degraded sources produce warnings, not failures.

### `get_opportunity_details`
**required:** `reference`. Routes automatically: references matching `AB-YYYY-NNNNN` go to the live APC public detail API; everything else searches the cached CanadaBuys snapshot by reference or solicitation number (substring match). Returns a full markdown dossier: overview, regions/commodity codes, description, submission details, source links.

### `list_deadlines`
Opportunities closing soon across both sources. Args: `days` (30; 1–365), `source`, `province`, `category`, `limit` (20; 1–50). Sorted soonest-closing first with days-remaining annotations.

### `find_matching_opportunities`
Ranks both sources against the saved business profile. Args: `days` (60; 1–365), `limit` (15; 1–30). Requires `set_business_profile` first. Scoring is deterministic: title keyword hits (10 pts each), description hits (5), UNSPSC/commodity matches (15/8), delivery-region match (10), closing within 14 days (+5). Each result explains *why* it matched.

### `daily_bid_brief`
The flagship free tool: market snapshot (open federal + Alberta counts), best-fit matches with reasons, closing-soon list, and one suggested action. Args: `days` (14; 1–60), `limit` per section (5; 1–10). Requires a saved profile.

---

## Business Profile Tools

### `set_business_profile`
**required:** `description` (what the business does). Optional: `company_name`, `location`. Extracts up to 20 capability keywords, infers industries (steel, lumber, aluminum, construction) from a curated keyword map, and persists to `profile.json`. Single-tenant: one profile per deployment.

### `get_my_profile`
Shows the saved profile: company, location, description, detected industries, keywords used for matching.

### `find_opportunities`
Federal-only profile matching (predecessor of `find_matching_opportunities`). Args: `days` (60), `limit` (15).

---

## Alberta Purchasing Connection Tools

All APC tools hit `https://purchasing.alberta.ca/api` live per request (no cache).

| Tool | Purpose | Key args |
|---|---|---|
| `search_alberta_opportunities` | Search APC postings | `keywords`, `category` (services/goods/construction), `status` (default OPEN), `limit` (10; 1–50) |
| `get_alberta_opportunity_details` | Full posting by reference — **required:** `reference` (`AB-YYYY-NNNNN`) | — |
| `list_alberta_deadlines` | Open postings closing within `days` (30; 1–365) | `category`, `limit` (20; 1–50) |
| `summarize_alberta_opportunities` | Open counts total and by category | none |
| `find_alberta_opportunities` | Profile-matched APC postings (searches top 8 profile keywords, dedupes, scores) | `days` (60), `limit` (15; 1–30) |

APC covers Government of Alberta plus municipalities, school boards, health entities, and post-secondary institutions.

---

## Legacy CanadaBuys Tools

Federal-only tools kept for backwards compatibility; prefer the unified tools.

| Tool | Purpose |
|---|---|
| `search_contracts` | Keyword/province search of the cached federal snapshot (`limit` 10) |
| `get_contract_details` | Federal detail by reference — **required:** `reference` |
| `list_upcoming_deadlines` | Federal closings within `days` (30) |
| `summarize_contracts` | Snapshot totals + sample titles + last-updated |
| `refresh_data` | Re-download the full CanadaBuys open-tender CSV (~120 s timeout) into the local cache |

The cache self-heals: unified tools refresh it automatically the first time they find it empty.

---

## Sandbox & Model Tools

### `process_bid_room`
**required:** `reference`. The heavy tool: boots an E2B sandbox, downloads up to `max_attachments` (5 cap) tender attachments, extracts text from PDF/DOCX/XLSX/ZIP (25 MB/file cap), then runs Cohere Command A+ *inside the sandbox* with read-only evidence tools and a strict JSON schema. Returns a structured review: bid recommendation, fit score, requirements, risks, missing information, deadlines, questions to ask, next actions. Optional: `business_context` (defaults to saved profile), `timeout_seconds` (900), `command_timeout_seconds` (420). Requires `E2B_API_KEY`; without `COHERE_API_KEY` it still extracts and returns evidence, skipping the model review. REST route `/bid-room/process` returns the full JSON artifact envelope instead of markdown.

### `analyze_contract_with_cohere`
**required:** `reference`. Lightweight model review of a cached federal tender (no sandbox, no attachments): fit, why it may be worth a look, risks/missing details, next actions. Optional: `business_context`, `question`, `max_tokens` (1200; 400–2000). Uses the Cohere failover chain (direct key → prod key → HF router).

### `check_cohere_status`
Reports which model route is configured (Cohere direct vs HF router), model IDs, endpoints, and key presence — without calling the model or revealing secrets.

---

## REST Convenience Routes

| Route | Method | Tool |
|---|---|---|
| `/health` | GET | liveness (no upstream calls) |
| `/tools` | GET | tool schemas as JSON |
| `/tools/{tool_name}` | POST | any tool, generic |
| `/search` | POST | `search_opportunities` |
| `/details/{reference}` | GET | `get_opportunity_details` |
| `/deadlines` | POST | `list_deadlines` |
| `/matches` | POST | `find_matching_opportunities` |
| `/brief` | POST | `daily_bid_brief` |
| `/bid-room/process` | POST | `process_bid_room` (JSON artifact) |
| `/profile` | POST / GET | `set_business_profile` / `get_my_profile` |
| `/cohere/analyze` | POST | `analyze_contract_with_cohere` |
| `/docs`, `/openapi.json` | GET | Swagger UI / OpenAPI schema |

REST responses wrap tool output as `{"tool": name, "content_type": "text/markdown", "content": "..."}`. Unknown tool names return 404; bid-room payload errors return 400; missing E2B/Cohere configuration returns 503.
