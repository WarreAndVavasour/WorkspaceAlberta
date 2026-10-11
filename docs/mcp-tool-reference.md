# MCP Tool & REST API Reference

Agents: call `get_server_guide` after connecting for the current workflow, handoff fields and data boundaries. See the [agent operating guide](agent-operating-guide.md).

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
**required:** `reference`. The heavy tool: boots an E2B sandbox, downloads up to `max_attachments` (5 cap) tender attachments (25 MB/file cap), then two Cohere layers run inside the sandbox. **Parse** (`parse-v5.0`, `POST /v2/parse`) turns PDF pages and images into structured markdown; DOCX/XLSX and Parse failures stay on the deterministic extractors. **Command A+** then reviews that evidence with read-only tools and a strict JSON schema. Returns a structured review: bid recommendation, fit score, requirements, risks, missing information, deadlines, questions to ask, next actions. The artifact lists which files used Parse vs fallback. Optional: `business_context` (defaults to saved profile), `timeout_seconds` (900), `command_timeout_seconds` (420). Requires `E2B_API_KEY`; the same `COHERE_API_KEY` covers Parse and the review. Without the key it still extracts with the fallback extractors and skips the model review. REST route `/bid-room/process` returns the full JSON artifact envelope instead of markdown.

### `classify_tender`
**required:** `reference`; optional `upload_token` (APC only). Lists the bidder requirements in a tender package. Tender PDFs (and PDFs inside ZIPs) are split into clauses with PyMuPDF in a separate OS process per file (no secrets in its environment; CPU, 1.5 GB memory and 60 s time limits; at most 2 at once); each clause gets a TypeSafe Jev L0 classification (response type, in bid?, mandatory?), each page a document-part classification, and clauses that pass both gates get an L1 sub-tag (with a reject option). Results merge into one requirement per canonical tag `<type>.<sub_tag>` with routing from the tag library (connector, answer source, lead time, question), pages and evidence quotes (≤240 chars). Limits: 800 pages, 8,000 clauses, 140 s per call (a result cut short is labelled `partial`). CanadaBuys: up to 5 public PDF or ZIP attachments (same URL resolution and public-HTTPS checks as the bid room; Word and Excel files are skipped). Alberta APC: the first call returns the bid room's private upload link; the uploads are not deleted, so `process_bid_room` can reuse the token. Requires `TYPESAFE_API_KEY`; without it the tool fails before any download. Pro. REST route `/bid-room/classify` returns the JSON artifact envelope (`{"artifact": ..., "markdown": ...}`). Code: `procurement_core/requirements/`.

**Output.** Over MCP the result has two text blocks and `structuredContent`, because some clients show the model only text content:

1. The markdown requirements table, ending with one sentence that says the JSON follows and how to use it (the procurement skill's requirements-board template, or a requirements board grouped by connector and lead time, counted back from `tender.closing`).
2. One line, `classify_tender JSON (schema wa.tender_requirements.v1):`, then the full artifact as compact JSON. It is the same object as `structuredContent`. Nothing is trimmed: about 30 requirements with 5 evidence quotes each come to roughly 60–90 KB, depending on document-name length.

Artifact fields (schema `wa.tender_requirements.v1`):

| Field | Notes |
|---|---|
| `schema` | Always `wa.tender_requirements.v1` |
| `reference`, `source` | The requested reference; `source` describes where the PDFs came from (`CanadaBuys public attachments` or `uploaded by the user from APC`) |
| `tender` | `reference`, `source` (`apc` or `canadabuys`), `title`, `buyer`, `closing` (exactly as the source reports it), `closing_timezone` (how to read `closing`), `closes_at` (the same moment as ISO 8601 in Alberta time with its UTC offset, as in the search tools), `posting_url`. Built from the APC details or the CanadaBuys row the call already fetched; missing values are `null`. |
| `kind`, `status` | `tender_requirements`; `complete` or `partial` |
| `requirements[]` | `id`, `tag`, `answer_source`, `lead_time`, `connector`, `question`, `mandatory`, `pages[]`, `evidence[]` (≤5 quotes of ≤240 chars with document and page), `evidence_units`, `headline` |
| `documents`, `counts`, `cost`, `model`, `prompt_versions`, `limits`, `elapsed_seconds`, `warnings` | Files read, pipeline counts, classifier usage and any limits or skipped files |

For an APC reference without `upload_token`, `structuredContent` is the upload link (`upload_required`, `upload_url`, `upload_token`, `expected_documents`), repeated as a second text block after the line `classify_tender JSON (upload link; no requirements yet):`. Errors return a single text block.

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
| `/bid-room/classify` | POST | `classify_tender` (JSON artifact) |
| `/profile` | POST / GET | `set_business_profile` / `get_my_profile` |
| `/cohere/analyze` | POST | `analyze_contract_with_cohere` |
| `/docs`, `/openapi.json` | GET | Swagger UI / OpenAPI schema |

REST responses wrap tool output as `{"tool": name, "content_type": "text/markdown", "content": "..."}`. Unknown tool names return 404; bid-room payload errors return 400; missing E2B/Cohere configuration returns 503.
