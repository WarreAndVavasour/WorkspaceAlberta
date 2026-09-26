# workspaceAlberta directory submission

Status as of September 26, 2026: **submitted; In review** in the corporate
Warre & Vavasour account. The owner completed the final submission in Chrome.
The [submission dashboard](https://claude.ai/directory/manage/workspacealberta)
shows Live as not yet reached. Deployment is complete; directory acceptance is
pending.

Saved authentication is **Required when the server asks** with **Client ID
Metadata Document**. The overview's legacy authentication summary says None,
but the full editor confirms the on-demand OAuth configuration is saved.

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

API ownership is declared as **We proxy a partner's API with permission**.
The owner confirmed existing APC permission on September 26, 2026; the underlying
permission document was not inspected or uploaded in this session. Keep that
record available for reviewers. CanadaBuys tender notices are published under
the [Open Government Licence – Canada](https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2).
APC's [copyright statement](https://purchasing.alberta.ca/legal#copyright)
requires permission unless otherwise specified. An extra proxy deployment
would not itself create permission and is not needed for this declaration.

## Evidence and reviewer access

Production is on revision `workspacealberta-google-live-faca0c611e08`.
The [rollout record](connector-readiness.md) includes the image digest, database
and secret setup, real Google callback/consent/token/refresh checks, and public
preflight results. Claude's corporate submission connection succeeded and
discovered 26 tools. The production title fix supplies `annotations.title` as
well as the top-level title; no callable tool names changed.

All 26 tools returned successful live responses through official MCP Inspector
2.8.0, including every Pro tool. The separate complimentary review tenant has a
fictional company profile and a public opportunity in its watchlist. Its key is
stored in Secret Manager and was shared in Anthropic's private test setup
instructions with the owner's explicit approval. The saved instructions and
credential were verified after reloading; the temporary plaintext handoff file
was removed. The instructions describe the completed tests and populated
account; the self-test checkbox is checked.

The E2B test used the public CanadaBuys notice for `MX-443841357513` and closed
the sandbox successfully. No first-party attachment was available, so the test
did not exercise PDF parsing. `AB-2026-06542` was used for the APC details,
watchlist and scoring checks. These results establish successful tool calls,
not a guarantee of model-output accuracy or complete coverage of all inputs.
Never commit reviewer credentials or use the owner's corporate login as shared
reviewer access. Revocation instructions are in the rollout record.

Directory acceptance is Anthropic's decision after submission. This integration
also remains usable by compatible MCP clients; it does not create billing through
Claude or establish compatibility with unreleased clients.
