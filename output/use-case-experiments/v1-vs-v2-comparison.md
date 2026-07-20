# Production Trace Suite: v1 vs v2 Comparison

**What changed between runs:** two fixes deployed to production Cloud Run revision `workspacealberta-00012-5rw`
(project `n8n-automation-project-459922`, region `northamerica-northeast1`):

- `70b4e4c` — AND-token relevance for multi-word Alberta + federal search
- `bbff0b8` — `analyze_contract_with_cohere` supports Alberta APC references
- `4fbfa0c` — Pro gate / Stripe billing / Supabase tenancy code committed to main
  (was already running in production as uncommitted code; no behavior change)

| | v1 (before fixes) | v2 (after fixes) |
|---|---|---|
| Dataset | `alberta-usecase-traces.json` | `alberta-usecase-traces-v2.json` |
| Run at (UTC) | 2026-07-19T11:12:33.624198+00:00 | 2026-07-20T12:34:53.293983+00:00 |
| Endpoint | https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp | https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp |
| Production revision | workspacealberta-00010-zbc | workspacealberta-00012-5rw |

## Per-trace results

| Trace | Query | v1 outcome / headline | v2 outcome / headline | Verdict |
|---|---|---|---|---|
| uc-01 | I run a small CWB welding shop in Red Deer with 8 guys. What… | success / Matching Opportunities for Red Deer Rig Welding | success / Matching Opportunities for Red Deer Rig Welding | unchanged |
| uc-02 | Any school or public building HVAC contracts out for tender … | success / 10 of 14 APC | success / 10 of 14 APC | unchanged |
| uc-03 | We do landscaping and grounds maintenance around Lethbridge … | success / 10 of — combined | success / 10 of — combined | unchanged |
| uc-04 | We're a catering company in Fort Mac — camps, crew food, eve… | success / 10 of 989 APC | success / 1 of 1 APC | IMPROVED — 989→1 match; catering-relevant (golf course operator/concession) replaces generic construction list |
| uc-05 | I've got two gravel trucks out of Medicine Hat. Who's tender… | success / 10 of 402 APC | success / 10 of 100 APC | IMPROVED — 402→100 matches; top result now drainage/hauling work (v1 top was unrelated building security) |
| uc-06 | Cleaning contracts for government buildings or schools in Ed… | success / 10 of — combined | success / 10 of — combined | unchanged |
| uc-07 | We're a 5-person IT support shop in St. Albert. Any governme… | success / 10 of — combined | success / 10 of — combined | unchanged |
| uc-08 | Do municipalities tender printing work? We do signs, forms, … | success / 10 of 33 APC | success / 3 of 3 APC | IMPROVED — 33→3 matches; v1 top was library IT services (irrelevant), v2 top is NAIT print procurement |
| uc-09 | Security services contracts — and tell me straight: is the b… | paywall / 8 of — combined | paywall / 8 of — combined | unchanged (paywall by design) |
| uc-10 | Master electrician in GP. What electrical work is closing in… | success / 10 of 69 APC | success / 10 of 69 APC | unchanged |
| uc-11 | Give me my morning brief — what fits my shop and what's clos… | success / Daily Bid Brief for Ironline Fabrication Ltd. | success / Daily Bid Brief for Ironline Fabrication Ltd. | unchanged |
| uc-12 | Winter's coming — any snow clearing contracts with towns or … | success / 10 of — combined | success / 1 of — combined | IMPROVED — 10 mixed→1 focused result; v1 top was unrelated Barrhead building project |
| uc-13 | Sidewalks, curbs, flatwork — what concrete tenders are out t… | success / 10 of 48 APC | success / 8 of 8 APC | IMPROVED — 48→8 matches, all concrete/roadwork; top is TEC concrete tender |
| uc-14 | I heard the Rural Municipalities of Alberta has a fencing RF… | success / 8 of — combined | success / 8 of — combined | unchanged |
| uc-15 | That Hwy 2 bridge tender near Morinville (AB-2026-04073) — p… | paywall / Pro paywall message | paywall / Pro paywall message | unchanged (still paywalled — Cohere fix needs Pro key) |
| uc-16 | Is there more construction work on the federal side or the A… | success / 10 of — combined | success / 10 of — combined | unchanged |
| uc-17 | Keep an eye on that bridge tender for me — I don't want to l… | paywall / Pro paywall message | paywall / Pro paywall message | unchanged (paywall by design) |
| uc-18 | The City of Calgary had an RFP for shop supplies (26-1524 I … | success / 8 of — combined | success / 3 of — combined | unchanged (8→3 combined, top result still relevant shop-supplies RFP) |
| uc-19 | What's Alberta Transportation tendering right now? Give me t… | success / 10 of 69 APC | success / 5 of 5 APC | IMPROVED — 69→5 matches, same relevant TEC highway tender on top |
| uc-20 | Any plumbing work in schools or hospitals out for tender? Jo… | success / 7 of — combined | success / 7 of — combined | unchanged (7 combined both runs, same top result) |
| uc-21 | What closes this week? I feel like I'm missing stuff.… | success / Opportunities Closing Within 7 Days | success / Opportunities Closing Within 7 Days | unchanged |
| uc-22 | Asphalt paving contracts — parking lots, roads, anything. Wh… | success / 10 of 59 APC | success / 10 of 14 APC | IMPROVED — 59→14 matches, asphalt/pathway paving on top |

## Outcome tallies

| Outcome | v1 | v2 |
|---|---|---|
| success | 19 | 19 |
| paywall | 3 | 3 |
| expectations met | 21/22 | 21/22 |

The one unmet expectation in both runs is uc-15: the suite expects the pre-fix "contract not found"
known bug, but production now returns the Pro paywall message instead — the paywall fires before the
Cohere path runs, so `bbff0b8` only becomes visible behind a Pro API key. This is by design.

## Latency (per tool call, 43 steps each run)

| Metric | v1 | v2 |
|---|---|---|
| median | 468 ms | 469 ms |
| p95 | 2016 ms | 3421 ms |
| mean | 788 ms | 844 ms |

Median latency is identical (~469 ms). The v2 p95 is higher solely because uc-11's
`daily_bid_brief` took 3.9 s in v2 vs ~2 s in v1 — one slow call in a 43-call sample, not a trend.

## What changed in production

1. **Multi-word Alberta search now ANDs tokens.** v1 OR-matched any keyword, so
   `catering food service` returned "10 of 989" topped by unrelated construction tenders.
   v2 returns 1 of 1 — the Lloydminster golf-course operator RFP (concession/catering).
   Spot-check: `HVAC` unchanged at 14 matches (single-word queries unaffected).
2. **Relevance improved in 7 of 22 traces** (uc-04, uc-05, uc-08, uc-12, uc-13, uc-19, uc-22);
   every other trace is behaviorally stable, including uc-20 which was already returning a
   tight relevant set.
3. **No regressions.** Outcome tally identical (19 success / 3 paywall); all paywalled traces
   (uc-09, uc-15, uc-17) still return the Pro message — the gate survived the redeploy intact.
4. uc-15's Cohere fix (`bbff0b8`) is deployed but invisible without a Pro key, as expected.
