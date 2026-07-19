# Regression — Finding #1: Multi-Word Search Relevance

**Date:** 2026-07-19 · **Fix:** AND-token coverage ranking in `procurement_core/service.py` (deterministic, no LLM) · **Method:** the exact search calls from the 5 affected traces in [`alberta-usecase-traces.json`](alberta-usecase-traces.json) re-run against a **local** stdio server (`mcp-servers/canadabuys/server.py`, `CANADABUYS_DATA_DIR` pointed at a temp dir) via [`rerun_finding_1.py`](rerun_finding_1.py); raw outputs in [`rerun-finding-1-results.json`](rerun-finding-1-results.json). The hosted Cloud Run endpoint still runs the old code and was not used.

**How the fix works:** multi-word queries are tokenized (lowercase, tokens ≥ 3 chars, stopwords dropped), and each APC row is scored by the fraction of tokens present in its searchable text (title + description + organization + commodity titles). Rows with **full** token coverage are kept, newest first. If no row has full coverage, the tool falls back to best-coverage ranking and says so in a `## Warnings` line — it never returns nothing when the API found rows. Single-keyword queries pass through unchanged. The federal matcher now requires all tokens to appear (any order) instead of a whole-phrase substring.

**Caveat:** APC is a live dataset — postings opened/closed between the trace capture and this re-run, so absolute counts are not directly comparable; the point is relevance of what comes back.

## Before vs after

| Trace | Query | Before (match count) | Before top-3 | After (match count) | After top-3 |
|---|---|---|---|---|---|
| uc-04 | `catering food service` (Alberta) | **989** APC records | 1. Strathcona County — RFPQ #26.0070 CITP Woodbridge Way…<br>2. Lac La Biche County — Economic Development Marketing Strategy<br>3. City of Lethbridge — HVAC Upgrade Stan Siwik Pool | **1** APC record | 1. City of Lloydminster — Lloydminster Golf Course Operator Services (catering/food service in scope) |
| uc-05 | `gravel supply hauling` (Alberta) | **402** APC records | 1. Infrastructure — BARRHEAD Provincial Building Replace Security Access<br>2. MD of Greenview — Negotiated RFP (newest posting)<br>3. MD of Greenview — Negotiated RFP (newest posting) | Fallback: best-coverage ranking of scanned window (10 shown) with warning | 1. City of Lloydminster — Northwest Drainage Channel Phase 4 (gravel in scope)<br>2. Epcor — RFP 203611 Wastewater Hauling<br>3. Forestry and Parks — Permanent Sample Plot Measurements |
| uc-08 | `printing signs` (Alberta) | **33** APC records | 1. St Albert Public Library — Managed IT Services<br>2. Town of Taber — Facility Naming Rights<br>3. Athabasca Chipewyan First Nation — Administration Building | **3** APC records | 1. NAIT — SCM26-… (printing + sign coverage)<br>2. MD of Wainwright — Notice of Proposed …<br>3. MD of Wainwright — Notice of Proposed … |
| uc-12 | `snow removal ice control` (unified, AB) | 10 combined | 1. Infrastructure — BARRHEAD Security Access<br>2. TEC — Erosion Repair<br>3. TEC — Grading, Granular… | **1** combined | 1. Kinetic GPO — NOI 2026 (snow/ice control coverage) |
| uc-20 | `plumbing` (unified, AB, single keyword) | 7 combined | 1. City of Edmonton — Boiler & Heating Chemical Supply<br>2. City of Red Deer — In-Line Condition Assessment<br>3. Infrastructure — EDSON Tourist Info Centre | **7** combined — **identical** | 1. City of Edmonton — Boiler & Heating Chemical Supply<br>2. City of Red Deer — In-Line Condition Assessment<br>3. Infrastructure — EDSON Tourist Info Centre |

## Verdicts

- **uc-04 — FIXED.** 989 → 1; the lone survivor is a food-service operator RFP. The "catering food service" flood is gone.
- **uc-05 — IMPROVED (fallback path).** No row in the scanned window contains all three tokens (only 2 of 100 even mention "gravel" — gravel work is seasonal), so the tool ranks best partial matches and discloses the fallback in `## Warnings` instead of dumping the newest 100 postings. Top hits now actually involve gravel/hauling.
- **uc-08 — FIXED.** 33 → 3, all with printing + sign(s) in their searchable text; IT-services and naming-rights noise eliminated.
- **uc-12 — FIXED.** 10 irrelevant → 1 relevant (full snow/removal/ice/control coverage). Federal rows with all tokens: none — consistent with the old whole-phrase check, minus the false confidence of 10 padded results.
- **uc-20 — UNCHANGED, as required.** Single-keyword queries bypass the filter; identical count and identical top-3.

**Single-keyword sanity:** `HVAC` still returns "Showing 10 of 14 matching APC records" — the 14 from the original finding — with the same newest-first ordering. Unchanged.

## Tests

`tests/test_search_relevance.py` (new, 15 tests, no network): tokenization/stopwords, word-boundary and plural matching, coverage fractions, full-coverage ranking, recency ordering, fallback ranking + warning, searchable-text composition (description/organization/commodity titles), and the federal matcher's single-word vs multi-word behavior. Full suite: `python -m unittest discover -s tests` — **58 tests, OK**.
