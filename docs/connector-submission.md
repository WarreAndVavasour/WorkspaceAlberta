# workspaceAlberta directory submission

Status: prepared; live Google sign-in, production promotion and portal submission
must be completed before claiming a public listing.

## Listing copy

- Name: **workspaceAlberta**
- Short description: **Find Canadian public contracts and assess your next bid.**
- Server: `https://elbowsupknivesout.warreandvavasour.com/mcp`
- Website: `https://elbowsupknivesout.warreandvavasour.com/`
- Privacy: `https://elbowsupknivesout.warreandvavasour.com/privacy`
- Setup/support: `https://elbowsupknivesout.warreandvavasour.com/support`
- Icon source: `https://elbowsupknivesout.warreandvavasour.com/icon.svg`
- Contact: `christian@warreandvavasour.com`

Wouldn't it be great if the next contract was easier to find? workspaceAlberta
connects your AI client to CanadaBuys and Alberta Purchasing Connection. Search
open opportunities, check deadlines, inspect source postings and compare tenders
with your business. Pro adds saved watchlists, bid/no-bid scorecards and tender
document analysis. Verify requirements against the original posting before
bidding. The connector does not submit bids or contact buyers.

## Example use cases

| User prompt | Expected workflow |
|---|---|
| Find open Alberta construction opportunities closing in the next 30 days. | Search; return references, source links and closing dates; inspect the best matches. |
| Compare these opportunities for a small Alberta environmental consulting firm. | Match the business description to opportunities and explain fit, evidence gaps and next steps. |
| Add this tender to my watchlist and help me decide whether to bid. | Request sign-in and an active Pro subscription; save the selected opportunity and build a bid/no-bid scorecard. |

## Authentication and paid access

Public discovery and free tools are anonymous. Protected tools return HTTP 401
with MCP protected-resource metadata. Clients use OAuth authorization code with
PKCE S256, CIMD or dynamic registration, and refresh tokens. workspaceAlberta is
the issuer; Google provides upstream identity with only `openid email` scopes.
Gmail and Google Workspace accounts are supported. Signing in is not payment.
Pro entitlement comes from the active Stripe subscription matching the verified
email; an unpaid signed-in user receives a tool error rather than another login.

## Data handling for the application

Use the public privacy notice as the source for the portal answers. The service
handles tool inputs/results, verified Google identity, saved profiles/watchlists,
OAuth grants and subscription references. Cloud Run is in Montréal and Supabase
in Toronto. Cloudflare, Google identity, Stripe, Cohere, E2B, optional Hugging Face
routes and configured PostHog telemetry have separate processing arrangements.
Do not claim universal Canadian residency, zero retention, certifications or
third-party no-training guarantees that have not been established.

## Evidence and reviewer access

Record the deployed image digest and revision, public preflight, real Google
callback/consent/token/refresh checks, tool checks in the target client, and the
final portal confirmation. The readiness script alone does not prove a customer
can sign in. Supply a populated review account through the portal's secure
authentication fields when required; never commit reviewer credentials.

Directory acceptance is Anthropic's decision after submission. This integration
also remains usable by compatible MCP clients; it does not create billing through
Claude or establish compatibility with unreleased clients.
