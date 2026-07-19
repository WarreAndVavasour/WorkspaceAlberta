# WorkspaceAlberta — User Test Workflows

**Date:** 2026-07-18
**Status:** First pass complete — W1, W2, W3, W4 run live; W5, W6 verified at the paywall boundary
**Companion report:** [fresh-clone-report.md](fresh-clone-report.md)

This document defines the user tests for WorkspaceAlberta as repeatable workflows. Each workflow is written as a script a tester (or an agent) can run, with expected outcomes, what actually happened on 2026-07-18, and the showcase moment it maps to.

The product under test: an MCP server that helps small Canadian businesses find more work — federal CanadaBuys tenders plus Alberta Purchasing Connection opportunities — through an AI assistant, with a free daily bid brief and paid ($85 CAD/mo Pro) bid-work tools.

---

## Personas

| ID | Persona | Who they are | What "more work" means to them |
|----|---------|--------------|-------------------------------|
| P1 | **Owner-operator fabricator** | Runs a 12-person CWB-certified metal fab shop in Edmonton. No estimator. Finds work by word of mouth. | Seeing the right tender before the deadline is already too close |
| P2 | **Estimator at a mid-size contractor** | Bids 5–15 public tenders a month. Lives in portals and PDFs. | A bid/no-bid call in minutes, not a lost afternoon |
| P3 | **Non-technical shop owner** | Has never heard of MCP, pip, or JSON. Uses a phone more than a laptop. | "Someone just tells me what to bid on" |
| P4 | **Bid consultant** | Writes bids for several small clients across sectors. | Watching many opportunities across many profiles at once |

---

## W1 — First-Run Setup (fresh clone)

**Persona:** P3 (with P1's patience)
**Goal:** Clone the repo and get the MCP server answering, using only public docs.
**Script:** `git clone` → read README → follow setup → install deps → run smoke test → wire into a client.

**Expected:** README leads a new user from zero to first live search in under 15 minutes.

**Actual (2026-07-18, full log in fresh-clone-report.md):**

- Clone: 5.4 s, 63 MB. ✅
- `pip install -r requirements.txt`: clean on Windows, 49 s. ✅
- Smoke test `tests.test_canadabuys_mcp_smoke`: **PASSED** (also `test_procurement_http_app`, 7/7 on full discover, E2B skipping cleanly without keys). ✅
- Server starts, speaks MCP, 21 tools, first live search in ~2 s. ✅
- **FAIL — README has zero setup steps.** The only install/run path lives in `docs/codex-setup.md`, written for AI agents. A business owner never finds it.
- **FAIL — naming confusion.** WorkspaceAlberta / canadabuys / "Build Canada" all name the same product; `.cursor/mcp.json` has two overlapping entries; `mcp.json.example` has three blocks with no "pick this one."
- **FAIL — maintainer-machine leakage.** Public docs reference `/home/chris/.local/bin/gbrain`, `C:\Users\chris\wvsetup`, and a private repo.
- **Note:** a working hosted-endpoint path exists (Cloud Run, ~2 min setup) but is buried in `mcp.json.example`. For P3 this hosted path is *the* product — it should be the README's front door.

**Verdict:** The wiring works; the welcome mat doesn't. Pass for a developer, fail for P3.

---

## W2 — Profile to First Matches ("five minutes to value")

**Persona:** P1 — Ironline Fabrication Ltd., Edmonton (structural steel, stairs, railings, platforms, CWB welding)
**Goal:** Describe the business once, in plain language, and immediately see ranked opportunities.
**Script:** `set_business_profile` → `find_matching_opportunities`

**Expected:** Keywords auto-detected; ranked list with scores, reasons, and closing dates.

**Actual (live, 2026-07-18):** ✅ **PASS — this is the best moment in the product.**

- Profile saved; auto-detected industry `steel` and 10 search keywords from a plain-English description.
- 8 ranked matches returned. Top: Alberta Transportation ITB `AB-2026-04073` (Hwy 2 interchange, structural steel girder bridge) — **score 91, closes in 11 days**, with transparent "why it matches" reasons.
- CanadaBuys cache refreshed itself on first use; graceful warning.

**Showcase beat:** the owner types one sentence about his shop and 30 seconds later is looking at a real bridge tender with his name written all over it. *This is the hero shot.*

---

## W3 — The Daily Brief Habit (free tier)

**Persona:** P1, morning coffee routine
**Goal:** One call that answers "what's out there, what fits me, what closes soon."
**Script:** `daily_bid_brief`

**Expected:** Market snapshot + best fits + closing soon + a suggested action.

**Actual (live, 2026-07-18):** ✅ **PASS.**

- Snapshot: 850 federal open notices, 1,523 Alberta open opportunities.
- Best fits reused profile ranking (score 91 bridge tender on top).
- Closing-soon section surfaced items 1 day out.
- Ends with a plain next action: "Open the top one or two matches, check mandatory requirements, make a bid/no-bid call."
- Free, no key required — matches the "free brief, paid bid work" model exactly.

**Showcase beat:** the 7:00 AM brief — replaces 45 minutes of portal-checking with one screen.

---

## W4 — Deep Dive on a Tender

**Persona:** P1 or P2
**Goal:** From a reference number, get everything needed to decide whether to read the full package.
**Script:** `get_opportunity_details(reference=AB-2026-04073)`

**Expected:** Buyer, dates, commodity codes, quantities, mandatory requirements, submission method, link.

**Actual (live, 2026-07-18):** ✅ **PASS — surprisingly rich.**

- Full quantities (279,400 m³ excavation, 57,000 t asphalt, HP 310x110 piling, reinforcing steel), pre-tender meeting dates, named procurement contact, CoR mandatory requirement, bid-bond and email-submission rules, direct APC link.
- **Found issue (from fresh-clone test):** `analyze_contract_with_cohere` returns "Contract not found" for Alberta references that unified search hands to users — a genuine dead end at the exact moment an owner asks for AI review of an Alberta tender.

**Showcase beat:** "no more digging a 140-page RFP for the three numbers that matter."

---

## W5 — Bid/No-Bid Decision (Pro gate)

**Persona:** P2
**Goal:** Fast deterministic go/caution/no-go on a reference.
**Script:** `bid_no_bid_scorecard(reference=AB-2026-04073)`

**Expected:** Free tier: clear, graceful upsell. Pro tier: scorecard with profile fit, runway, region match, verdict.

**Actual (live, 2026-07-18):** ✅ **PASS at the boundary — the paywall is the product working.**

- Without a Pro key: "WorkspaceAlberta Pro required … subscribe at Stripe ($85 CAD/month)" — actionable, no crash, no ambiguity.
- Pro-tier output untested in this pass (needs a `wa_live_...` key).

**Showcase beat:** this IS the pricing story made visible — browsing is free forever; the meter starts the moment you decide to actually bid. A video should *show the paywall*, not hide it.

---

## W6 — Watchlist Tracking (Pro gate)

**Persona:** P1/P4
**Goal:** Pin an opportunity with a note; get closing-date countdowns.
**Script:** `watch_opportunity(AB-2026-04073, note)` → `list_watchlist`

**Actual (live, 2026-07-18):** Same graceful Pro gate as W5. Untested past the boundary in this pass.

---

## Findings Summary

| # | Finding | Severity | Workflow |
|---|---------|----------|----------|
| 1 | README has no Getting Started; setup only in agent-oriented `docs/codex-setup.md` | **Blocker for P3** | W1 |
| 2 | Hosted Cloud Run endpoint is the 2-minute path for non-developers but is buried in `mcp.json.example` | High | W1 |
| 3 | Naming: WorkspaceAlberta / canadabuys / Build Canada used interchangeably | High | W1 |
| 4 | `analyze_contract_with_cohere` dead-ends on Alberta references ("Contract not found") | High | W4 |
| 5 | Maintainer paths and private-repo references leak into public docs | Medium | W1 |
| 6 | Pro paywall is clean, graceful, and correctly placed (scorecard, watchlist) | Working as designed | W5/W6 |
| 7 | Free tier (profile → matches → brief → details) is genuinely useful standalone | Strength | W2–W4 |

---

## Showcase Map — which workflow becomes which asset

| Workflow | Product story | Suggested asset |
|----------|---------------|-----------------|
| W2 | "One sentence about your shop → a ranked tender list in 30 seconds" | **Hero video (60–90 s)**: live screen capture, real persona, real tender |
| W3 | "The 7:00 AM brief replaces the portal-checking habit" | **Short vertical clip / animation**: brief appears with coffee; 850 federal + 1,523 Alberta counters tick up |
| W4 | "The three numbers that matter, out of the 140-page RFP" | **Deck slide or motion graphic**: PDF wall → extracted quantities card |
| W5 | "Free to look. $85/month to bid." | **Deck pricing slide**: show the actual paywall screen — honesty as a brand asset |
| W1 | "Two minutes to connect, no portal to babysit" | **Docs fix first**, then a setup GIF once the README earns it |
| W1 (P3) | "Built for trades, not tech" | **Positioning anchor for the deck**: the hosted endpoint means no install at all |

**Recommended narrative order for any asset:** W2 (magic) → W3 (habit) → W4 (depth) → W5 (business model). That sequence is the funnel: magic earns attention, habit earns trust, depth earns reliance, and the paywall converts at the moment of intent.

---

## Next test passes

1. **W5/W6 with a Pro key** — verify scorecard and watchlist outputs past the paywall.
2. **W1 repeat after README fix** — same fresh-clone script; target: P3 reaches first search in < 5 minutes via the hosted endpoint.
3. **P4 multi-profile test** — bid consultant managing several client profiles; likely surfaces profile-storage limits.
4. **`process_bid_room` live E2B test** — the heaviest Pro feature; needs `E2B_API_KEY` and a real tender package.
