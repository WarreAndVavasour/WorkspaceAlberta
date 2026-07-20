# Pricing & Subscription

## The model

Two tiers. The habit is free; the bid work is paid.

| | Daily Brief (Free) | WorkspaceAlberta Pro ($85 CAD/mo) |
|---|---|---|
| Daily bid brief | ✔ | ✔ |
| Unified search, details, deadlines | ✔ | ✔ |
| Bid rooms (E2B sandboxed package analysis) | — | ✔ |
| Cohere Command A+ tender review | — | ✔ |
| Watchlist + bid/no-bid scorecards | — | ✔ |
| Profile-matched ranking | ✔ (basic) | ✔ |

## Why $85

"Free MCP server" signals zero value to a business owner — it reads as a toy. $85/mo is priced against the alternative, not against software: one missed tender that fit the shop, or one estimator afternoon lost to a 140-page RFP package, costs more than a year of Pro. The price *is* the positioning: this is a tool for people who bid to win, and the number forces the pitch to be about payback, not features.

The daily brief stays free deliberately — it builds the daily habit and the trust that makes the upgrade obvious the first time an owner wants the documents read, not just listed.

## Stripe objects (live)

| Object | ID |
|---|---|
| Product | `prod_UpsvYr8M36rKof` (WorkspaceAlberta Pro) |
| Price | `price_1TqDAVIOLkCszIIOQIb7YgT3` — $85.00 CAD, monthly recurring |
| Payment link | `plink_1TqDBoIOLkCszIIOsXkMqW9Q` → https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a |

Promo codes are enabled on the payment link. The subscription page is `subscribe.html` at the repo root (single-file, brand palette from the homepage design spec).

## Provisioning (built)

The gate is implemented (see `procurement_core/auth.py`, `billing.py`, `storage.py` and the deployment guide):

1. **Per-customer API keys** — `wa_live_...` Bearer keys, SHA-256 hashed, validated against the `wa_subscribers` Supabase table with a 5-minute cache. Pro tools gated on REST and MCP; free tools stay open; subscribers get tenant-scoped profile/watchlist storage.
2. **Stripe webhooks** — `/stripe/webhook` verifies signatures and handles `checkout.session.completed` (issue key → Supabase row + Stripe customer metadata) and `customer.subscription.deleted` (revoke).
3. **Usage metering** — table has `bid_rooms_used_month` columns ready; enforcement middleware is still on the roadmap.

### Go-live checklist

- [ ] Apply `pipelines/migrations/001_create_wa_subscribers.sql` in Supabase
- [ ] Create the webhook endpoint in the Stripe Dashboard (Developers → Webhooks → Add endpoint → `https://<host>/stripe/webhook`, events: `checkout.session.completed`, `customer.subscription.deleted`); copy its signing secret
- [ ] Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_WEBHOOK_SECRET` (and optionally `STRIPE_SECRET_KEY`) on Cloud Run
- [ ] Redeploy; confirm `GET /health` shows `"gate": {"enabled": true}`
- [ ] Test checkout with a promo code; email the issued key (visible in the Stripe customer's metadata / `pending_key` column)

Welcome-email flow is manual for now — the plaintext key sits in `pending_key` and Stripe customer metadata until sent. Early Pro subscribers are design partners: manual onboarding, direct support, and their bid-room usage informs the metering limits.
