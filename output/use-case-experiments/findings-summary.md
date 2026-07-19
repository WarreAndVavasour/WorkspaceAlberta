# WorkspaceAlberta MCP — Findings from 22 Live User Traces

**Date:** 2026-07-19 · **Dataset:** [`alberta-usecase-traces.json`](alberta-usecase-traces.json) (22 traces, 43 tool calls, executed live against the deployed Cloud Run endpoint) · **Method:** realistic Alberta small-business prompts run end-to-end; prompt, tool calls, raw results, and final answers kept as single traces.

**Headline:** the core loop works. 19/22 traces returned real, relevant Alberta opportunities; the other 3 hit the Pro paywall cleanly. Zero transport errors. Median tool latency 468 ms, p95 ~2 s. The product is demo-ready for discovery; one search bug and one hidden dead-end cap the ceiling.

---

## Ranked by product impact

### 1. Multi-word keyword search is effectively broken — fix first
**Evidence:** `search_alberta_opportunities` with `"catering food service"` matched **989 of ~1,500** APC records; `"gravel supply hauling"` matched 402. Top results were simply the newest postings, not relevant hits. Single keywords behave correctly: `HVAC` → 14 matches, `printing signs` → 33, `concrete sidewalk curb` → 48, `electrical` → 69.
**Impact:** this is how real users talk ("camps and crew food", "sidewalks and curbs"). 5 of 22 traces (uc-04, 05, 08, 12, 20) returned noise on the first call.
**Fix:** AND semantics or ranked scoring for multi-word queries; at minimum document "use one keyword" and have the agent layer auto-decompose phrases into single-keyword searches.

### 2. The Cohere Alberta-reference dead-end is masked by the paywall — verify before selling Pro
**Evidence:** uc-15 (`analyze_contract_with_cohere` on `AB-2026-04073`) returned the Pro paywall in ~200 ms, *before* any contract lookup. The known "Contract not found" bug for Alberta references is unreachable without a Pro key — so it is currently untestable, and the first paying customer may be the one to find it.
**Fix:** with a Pro key present, run the Alberta-reference path once; the paywall currently fires ahead of the lookup, so order is fine — the lookup itself needs the Alberta branch fixed.

### 3. `summarize_alberta_opportunities` takes zero arguments — spec drift
**Evidence:** live schema shows no parameters; planned `keywords` filters in uc-07/uc-22 were silently dropped. The tool summarizes the whole Alberta market only.
**Impact:** low, but it breaks the "summarize my sector" agent pattern users will naturally attempt.
**Fix:** add an optional keywords/category parameter or document the limitation in the tool description so agents stop trying.

### 4. The paywall is doing its job — keep it, show it
**Evidence:** uc-09, uc-15, uc-17 (scorecard, Cohere review, watchlist) all return the identical, actionable "Pro required → Stripe $85 CAD/month" message in ~200 ms, not flagged as errors. Cleanest possible freemium boundary: browsing free, bid work paid.
**Note:** `list_watchlist` is also paywalled even when empty — consider letting an empty watchlist render with an upsell instead, so users see the feature exists.

### 5. Performance is demo-safe, with two heavy calls to watch
**Evidence:** median 468 ms across 43 calls; slowest were `daily_bid_brief` (4.8 s) and `find_matching_opportunities` (4.7 s) — the two hero features. Everything else ≤ ~2 s.
**Fix:** cache the brief per profile per day; consider a progress hint for calls over ~3 s.

### 6. Reference-chaining works end-to-end — the agent pattern is sound
**Evidence:** all `<ref-from-previous-step>` resolutions succeeded across 43 steps (`AB-2026-…`, `cb-…`, `MX-…` formats). Search → details → answer is a reliable two-step loop; uc-14 answered "materials only or install too?" verbatim from `AB-2026-04199` (RMA Fencing RFP, closing 2026-07-28).

---

## Trace outcomes

| Outcome | Count | Traces |
|---|---|---|
| success | 19 | uc-01–08, 10–14, 16, 18–22 |
| paywall (as designed) | 3 | uc-09, uc-15, uc-17 |
| known-bug reproduced | 0 | (uc-15 masked by paywall — see #2) |
| error | 0 | — |

Expectations met: 21/22.

**Suggested order of work:** #1 (search relevance) → #2 (verify Cohere path with a Pro key) → #3 (schema doc) → #5 (brief caching). Everything else is polish.
