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
| `keywords` | string | — | Matched against title, buyer, category, region, description, reference, UNSPSC, GSIN, trade agreements, procurement method, and selection criteria |
| `source` | string | `all` | `all`, `federal` (aliases: canadabuys, canada, national), `alberta` (alias: apc) |
| `province` | string | — | Region filter; a non-Alberta province skips the APC source with a warning |
| `category` | string | — | Free text for federal; mapped to APC codes (services→SRV, goods→GD, construction→CNST) for Alberta |
| `limit` | int | 20 | 1–50, combined across sources |

Results sort newest-posted first when the call is keywords only. Pass `description` or `profile` to run the supply-fit pass first: a UNSPSC, GSIN, and APC commodity-code prefilter (at most 12 notices), then one TypeSafe Jev classification per notice. Yes and partial results are ordered by that verdict, then by keyword score and any Buy Canadian bonus. A missing or rejected `TYPESAFE_API_KEY` falls back to keyword ranking and the result says so. Degraded sources produce warnings, not failures.

### `find_business_fit`
**required:** `description`. Optional `location`, `company_name`, `source`, `province`, `category`, `days` (120; 1–365), `limit` (15; 1–50), and an inline `profile`. Same fit pass as a described `search_opportunities`, aimed at a sentence such as "bakery in Red Deer, Alberta providing baking at scale and baking/culinary training." The description and a short notice summary are sent to TypeSafe when a key is configured. At most 12 classifications, 4 at a time, 8 seconds for the whole pass, and answers are cached per notice and description. About 500 input tokens per notice; Jev bills input only at $0.042 per million tokens.

### `get_opportunity_details`
**required:** `reference`. Routes automatically: references matching `AB-YYYY-NNNNN` go to the live APC public detail API; everything else searches the cached CanadaBuys snapshot by reference or solicitation number (substring match). Returns a full markdown dossier: overview, regions/commodity codes, description, submission details, source links.

### `list_deadlines`
Opportunities closing soon across both sources. Args: `days` (30; 1–365), `source`, `province`, `category`, `limit` (20; 1–50). Sorted soonest-closing first with days-remaining annotations.

### `find_matching_opportunities`
Ranks both sources against any business profile. Args: `days` (60; 1–365), `limit` (15; 1–30), plus an inline `profile` when nothing is saved. Scoring is deterministic and sector-neutral: title keyword hits (10 pts each), description hits (5), classification or commodity hits (8), legacy UNSPSC prefix hits for steel, lumber, aluminum, and construction (15), an industry label in the classification text (12), delivery-region match (10), closing within 14 days (+5), and a domestic-preference bonus (10) for a Canadian or Alberta business when the notice already matches on content. Each result explains *why* it matched. When the profile has a description, the first reason is the Jev fit verdict. Domestic preference alone does not create a keyword match; after a yes or partial verdict it still adds the Buy Canadian bonus for a Canadian business.

### `daily_bid_brief`
The flagship free tool: market snapshot (open federal + Alberta counts), best-fit matches with reasons, closing-soon list, and one suggested action. Args: `days` (14; 1–60), `limit` per section (5; 1–10). Uses a saved profile or an inline `profile`. Matched notices that carry a Buy Canadian or other domestic-preference flag say so on the line.

### `match_industrial_support_programs`
Public and read-only. Matches a description, an `industry`, a `location`, or an inline `profile` to `procurement_core/content/industrial_programs.json`. Covers the 21 October 2026 $8.72 billion federal-provincial package and national programs an Alberta firm can ask about (PrairiesCan Regional Tariff Response Initiative, ISED Strategic Response Fund, Canada Strong Diversification Fund, BDC Pivot to Grow, the BDC metals envelope, NRCan First and Last Mile Fund, the Critical Minerals Accelerator, and the PSPC Buy Canadian Policy Framework). Ontario-only streams are returned in their own section. An empty location is read as Alberta. This does not apply for funding or decide eligibility. REST route: `POST /industrial-programs`.

---

## Business Profile Tools

### `set_business_profile`
**required:** `description` (what the business does, in any sector). Optional: `company_name`, `location`. Extracts up to 20 capability keywords. Infers sector labels from a hint list that still includes steel, lumber, aluminum, and construction, and keeps a free-text label when the description matches none of those hints. Explicit `industries` on an inline profile are kept as given. Persists to `profile.json` for a signed-in tenant or a local install.

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

1. The markdown requirements table, ending with one sentence that says the JSON follows and how to use it (the procurement skill's requirements-board template, or a requirements board grouped by connector and lead time, counted back from `tender.closes_at`).
2. One line, `classify_tender JSON (schema wa.tender_requirements.v1):`, then the full artifact as compact JSON. It is the same object as `structuredContent`. Nothing is trimmed: about 30 requirements with 5 evidence quotes each come to roughly 55–60 KB. Document names appear once, in `documents`; pages and quotes point to them by `doc`.

Artifact fields (schema `wa.tender_requirements.v1`):

| Field | Notes |
|---|---|
| `schema` | Always `wa.tender_requirements.v1` |
| `reference`, `source` | The requested reference; `source` describes where the PDFs came from (`CanadaBuys public attachments` or `uploaded by the user from APC`) |
| `tender` | `reference`, `source` (`apc` or `canadabuys`), `title`, `buyer`, `closing` (exactly as the source reports it), `closing_timezone` (how to read `closing`), `closes_at` (the same moment as ISO 8601 in Alberta time with its UTC offset, as in the search tools), `posting_url`. Built from the APC details or the CanadaBuys row the call already fetched; missing values are `null`. |
| `kind`, `status` | `tender_requirements`; `complete` or `partial` |
| `requirements[]` | `id`, `tag`, `answer_source`, `lead_time`, `connector`, `question`, `mandatory`, `pages[]` (`{doc, page}`, first 20), `page_count`, `evidence[]` (≤5 quotes of ≤240 chars with `doc` and page, strongest first), `evidence_units` |
| `documents[]` | `doc` (the index that `pages` and `evidence` use), `document` (file name), `pages`, `pages_in_file`, `units` |
| `counts`, `cost`, `model`, `prompt_versions`, `limits`, `elapsed_seconds`, `warnings` | Files read, pipeline counts, classifier usage and any limits or skipped files |

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
| `/industrial-programs` | POST | `match_industrial_support_programs` |
| `/bid-room/process` | POST | `process_bid_room` (JSON artifact) |
| `/bid-room/classify` | POST | `classify_tender` (JSON artifact) |
| `/profile` | POST / GET | `set_business_profile` / `get_my_profile` |
| `/cohere/analyze` | POST | `analyze_contract_with_cohere` |
| `/docs`, `/openapi.json` | GET | Swagger UI / OpenAPI schema |

REST responses wrap tool output as `{"tool": name, "content_type": "text/markdown", "content": "..."}`. Unknown tool names return 404; bid-room payload errors return 400; missing E2B/Cohere configuration returns 503.
