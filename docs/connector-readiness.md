# Connector readiness and paid access

OAuth lets someone connect their workspaceAlberta account to an MCP client,
approve access, and use the tools their subscription permits. Public procurement
search stays open. The same server can serve Claude, Claude Code, and other
compatible clients; future Astra integration needs its published requirements
and client tests before we claim compatibility.

Claude and Claude Code are **OAuth clients**. WorkspaceAlberta is the
authorization server: it hosts the Google sign-in entry and consent pages, then
issues tokens to the client. Supabase stores the identity and grant state;
Google Cloud hosts the service. Google is the upstream identity provider, not
the MCP token issuer. Current
redirect rules allow Claude's hosted callbacks and native-client loopback
callbacks; another hosted client needs its callback requirements reviewed.

## What changed and why it matters

| Change | Why it matters |
|---|---|
| Escaped sign-in and consent pages | A registered client name, login ID, or backend error cannot insert executable HTML into the sign-in page. |
| Database migrations `002` and `003` | Identity and OAuth grants survive restarts. Atomic claims and a locked email-code verifier prevent replay and lost attempt counts across Cloud Run instances. |
| Restricted client-metadata fetching | Client discovery cannot follow redirects to internal services or switch DNS destinations after validation. HTTPS hostname checks and response-size limits remain enforced. |
| Shared signing secret | Every instance verifies the same access tokens. The key is stored in Secret Manager, outside git. |
| Google sign-in and migration `004` | Users prove identity through Google, then approve their MCP client. One-use browser-bound state and nonce/PKCE checks prevent login replay. Stable Google IDs avoid merging accounts by email. |
| Google client secret | Secret Manager supplies the web app credential to Cloud Run; customers and MCP clients never receive it. Google mode needs no SMTP credentials. |
| MCP tool titles and error results | Clients can display clear tool labels and distinguish subscription denials or backend failures from successful results. Callable identifiers stay unchanged. |

Supabase remains the existing Toronto **database**. Google sign-in requests
only identity and email, and supports Gmail and Google Workspace accounts.
It does not request Gmail, Drive or contact access. Google is not authoritative
for third-party email addresses attached to Google accounts, so those accounts
need a future independently verified linking flow before email-based paid access
can support them. SendGrid is set aside for corporate marketing, outreach and
inbound free requests; login does not subscribe anyone to marketing.
The application and database are hosted in Canada, while Google identity and
other service providers have their own processing arrangements. The public
`/privacy` page describes these boundaries and `/support` explains setup.

## Can customers pay to use this in Claude Code?

Yes: customers buy **workspaceAlberta Pro through our Stripe checkout**, then
sign in with the checkout email. The existing Stripe webhook updates their
subscription; the server checks that it is active before allowing Pro tools.
OAuth handles identity and permission, while Stripe handles the charge.

This code does not charge the customer's Claude balance, create Anthropic
revenue sharing, or meter individual tool calls. A 402 response means an active
subscription is required; it does not execute a payment. Claude Code can
[connect to remote MCP servers and authenticate with OAuth](https://code.claude.com/docs/en/mcp).

## What remains before a directory submission

Complete Google app configuration and the staged Cloud Run rollout, then test discovery,
sign-in, approval/denial, refresh, anonymous search, paid access, and an inactive
subscriber through the public endpoint. All 26 current tools now declare display
titles alongside their existing read-only/destructive annotations. The tool
identifiers remain unchanged for clients and harnesses. These titles are deployed
on the staging tag. Promote the tested revision and test each tool in Claude
before submission.
Prepare a privacy policy, support
contact, icon, setup instructions, and a populated reviewer account, then
submit through [Anthropic's developer portal](https://claude.com/docs/connectors/building/submission).
OAuth is part of readiness; merging this change does not publish a listing.

The harness should use discovery, PKCE, refresh, and reconnect against this same
endpoint. It does not need a copy of the server's authentication or billing code.

## Rollout record — 2026-09-26

The record below describes the earlier email-based staging revision. Google
sign-in supersedes that dependency; SendGrid troubleshooting is no longer a
prerequisite for this release. Deployment and directory approval remain separate
steps and must be recorded only after their live checks complete.

- Applied migrations `002` and `003` to the existing Toronto Supabase project,
  after a transaction rollback validation. Tested single-use grants and OTP
  concurrency against the real database; synthetic test rows were cleaned up.
- Created Secret Manager secret `workspacealberta-oauth-signing-key`, version
  `1`, replicated in Montréal; granted the existing Cloud Run runtime access.
- Configured SendGrid with verified sender `christian@warreandvavasour.com`.
  Replaced the displayed setup key with a Mail Send-only key, stored as
  `workspacealberta-smtp-password:2`; revoked the setup key and disabled secret
  version `1`. Neither active secret value is in git or the transcript.
- Deployed commit `a504340131ec` as revision
  `workspacealberta-oauth-a504340131ec`, tagged `oauth-ready`, with both secrets
  bound and **zero production traffic**. All 14 OAuth preflight checks passed,
  including 26 tool titles, anonymous access, protected-tool challenges, invalid
  refresh responses, and Claude Code CIMD authorization-page loading. The
  slowest individual preflight request took 0.50 seconds in this run.
- Live procurement checks passed on the tag: search 3.14 seconds, details 0.58
  seconds, and profile matching 3.91 seconds. Matching refreshed an empty
  CanadaBuys cache; no planner-fallback or partial-retrieval warning occurred.
  These timings are observations, not latency guarantees.
- The local HTTP authorization flow also passed against real Supabase with an
  in-process mail capture: consent, PKCE exchange, refresh rotation, and grant
  replay rejection. Its synthetic user and grant rows were removed and their
  removal checked. This does not verify real email delivery.
- The account dashboard shows an upgraded Email API plan and a paid invoice,
  but SendGrid's sending API still returns `401 Maximum credits exceeded`; SMTP authentication
  closes the connection. Email delivery and the real sign-in flow remain
  unverified. Resolve the provider's sending-credit state before traffic promotion;
  [SendGrid advises contacting support](https://support.sendgrid.com/hc/en-us/articles/35466138799899-Understanding-the-Maximum-Credits-Exceeded-error)
  when this persists after the correct plan and payment are confirmed. Email
  troubleshooting and the support message are deferred at the owner's request.
- Production remains on APC revision `workspacealberta-apc-e3b174942ae2`.

Validation: 151 local tests passed, with eight integration tests skipped
by default. All eight opt-in tests passed separately, including the real Supabase
HTTP flow. GitHub smoke checks passed for the deployed code. The stale adapter
contract tests were repaired and added to CI. Syntax/import and whitespace
checks passed. The injection, replay,
concurrent-claim, and private-destination triggers no longer reproduce;
existing PKCE, refresh, anonymous tools, and legacy-key gating tests still pass.

Operational details and verification commands are in [OAuth deployment](oauth.md).
