# Tooling Roadmap

Proposed MCP tools, API extensions, and integrations — prioritized by what makes WorkspaceAlberta easier to use, understand, and deploy, and by what justifies the $85/mo Pro tier. Status legend: ✅ scaffolded in `procurement_core/extensions.py` · 📋 planned.

## Tier 1 — Retention & daily value (build first)

### ✅ `watch_opportunity` / `list_watchlist` / `unwatch_opportunity`
Save any opportunity to a persistent watchlist with an optional note. The daily brief gains a "Watched" section with days-to-close. This is the retention loop: a user with 6 watched tenders does not cancel their subscription.

### ✅ `bid_no_bid_scorecard`
Deterministic bid/no-bid checklist for a reference: profile fit score, days runway vs. estimated response effort, buyer type, region match, and an explicit go/caution/no-go verdict with reasons. The free cousin of the Cohere review — fast, reproducible, no model cost. Upsell path: "run `process_bid_room` for the full document-grounded review."

### 📋 `saved_search_alerts`
Named saved searches (`create_alert`, `list_alerts`, `run_alerts`) that diff against the previous run and report only *new* postings. Pairs with a scheduler (cron / Cloud Scheduler hitting `POST /tools/run_alerts`) and an email/Slack sink. This is the single strongest Pro feature: "never miss a tender again."

### 📋 `amendment_tracker`
Track amendments/addenda on watched opportunities. CanadaBuys publishes amendment data; a changed closing date on a watched tender is exactly the alert an estimator pays for.

## Tier 2 — Bid work acceleration

### 📋 `requirements_checklist_extractor`
From a bid-room artifact, emit a compliance matrix (requirement → evidence needed → status) as markdown and CSV. Turns the Cohere review into a working document an estimator actually fills in.

### 📋 `bid_calendar`
`get_bid_calendar` returning watched + matched deadlines as an iCal feed (`/calendar.ics` REST route). Deadlines appear in Outlook/Google Calendar where owners already live.

### 📋 `win_history` / outcome tracking
Record bid/no-bid decisions and outcomes per reference. Over time this powers hit-rate reporting and sharpens matching (boost keyword weights on won work).

### 📋 `similar_awards_lookup`
Query CanadaBuys award history for similar past contracts: who won, award values, incumbent patterns. Answers "what does this usually go for?" — high perceived value for pricing bids.

## Tier 3 — Platform & deployment extensions

### 📋 Multi-user profiles + API keys
Prerequisite for hosted Pro: per-customer profile storage keyed by API key (header `X-WA-Key`), replacing the single `profile.json`. Stripe webhook (`checkout.session.completed` → issue key; `customer.subscription.deleted` → revoke) closes the billing loop. See `docs/authentication-and-multi-user-model.md`.

### 📋 Usage metering middleware
Count tool calls per key (free tier: brief + search; Pro: everything + N bid rooms/month). Exposed at `/usage`, enforced in `run_tool`.

### 📋 Webhook/event sink tool
`configure_notifications` (email via Resend/SES, Slack webhook, SMS via Twilio) so alerts and daily briefs push instead of pull. The brief becomes an email product — the habit loop without opening any tool.

### 📋 More sources, same shape
The unified normalizer makes new sources cheap: BC Bid, SaskTenders, Manitoba, MERX (public layer), municipal portals. Each is one client + one `normalize_*` function. "All Canadian public demand in one MCP server" is the moat.

### 📋 `npx` one-line install polish
`packages/workspace-alberta-mcp` already wraps the server for npm. Finish: `npx workspace-alberta-mcp` prompts for keys, writes client config for Claude Desktop/Cursor automatically, runs the smoke test. Deployment friction is the #1 adoption killer for MCP servers.

### 📋 OpenAPI → GPT Actions / Gemini extensions manifest
The REST mirror already exists; publishing a tuned OpenAPI subset lets non-MCP assistants (ChatGPT, Gemini) use the same core. Widens the funnel beyond MCP-native users.

## Sequencing recommendation

1. Watchlist + scorecard (✅ scaffolded) → ship inside current single-tenant server
2. Saved-search alerts + scheduler + email sink → the Pro headline feature
3. Multi-user keys + Stripe webhook → actually collect the $85/mo at scale
4. Amendment tracking, bid calendar → retention deepeners
5. New provinces → market expansion
