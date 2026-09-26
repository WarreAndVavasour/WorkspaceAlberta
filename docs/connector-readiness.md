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
| MCP tool titles and error results | Clients can display clear tool labels and distinguish subscription denials or backend failures from successful results. Titles are supplied both at the top level and in `annotations.title` for directory compatibility. Callable identifiers stay unchanged. |

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

## Directory status and remaining review work

The owner submitted workspaceAlberta on September 26, 2026. The corporate
[submission dashboard](https://claude.ai/directory/manage/workspacealberta)
shows **In review**, not Live. The saved configuration uses OAuth on demand
with Client ID Metadata Documents. Public privacy, support and icon URLs are
included. The owner confirmed existing APC permission, so data handling is
declared as an authorized proxy; CanadaBuys uses its published open-data licence.

A separate, populated Pro reviewer account is provisioned. All 26 tools returned
successful live responses through MCP Inspector 2.8.0, including profile and
watchlist writes, scoring, Cohere analysis and an E2B bid room. That bid-room run
used public notice text; it did not test PDF parsing because no first-party
attachment was available for that tender. With the owner's approval, the reviewer
key was saved in Anthropic's private test setup instructions. Do not represent
the 14-check preflight alone as a test of every
tool or the submission as directory approval. See the
[submission record](connector-submission.md) for details.

The harness should use discovery, PKCE, refresh, and reconnect against this same
endpoint. It does not need a copy of the server's authentication or billing code.

## Rollout record — 2026-09-26

The archival sign-in/consent design is now live on revision
`workspacealberta-archive-fa746ae305f4` (100% traffic), from merged commit
`fa746ae305f434ae5768dabb32e935f0a20b9b22`, image digest
`sha256:997a9dd662f9814f955d36a670b6a4ae58310b87a319f6ca1e9bbb438bf5b546`.
Cloud Build ID: `54fb661e-909f-4d33-903b-c3798ecd415c`.
The previous Google revision below is the rollback target. OAuth/26-tool checks,
exact image hashes, the Google sign-in page and procurement acceptance passed on
both the candidate and the public endpoint. This presentation release did not
repeat the interactive Google token exchange; it preserves the tested runtime
environment, secret bindings, identity and canonical callback configuration.
See [Cloud Run releases](cloud-run-workflow.md).

### Initial Google sign-in rollout

Google sign-in initially went live on the canonical public endpoint with revision
`workspacealberta-google-live-faca0c611e08`, built from
commit `faca0c611e08` with image digest
`sha256:2d1409ed03037dc5592649245837c2d682108b5b3003d232df06edc49a9ee55f`.

- Migration `004` was validated and applied to the existing Toronto database.
  Real concurrent state claims produced exactly one winner; temporary test rows
  were removed.
- Cloud Run uses `WA_LOGIN_PROVIDER=google` and Secret Manager binding
  `workspacealberta-google-client-secret:1`, alongside the existing signing key.
  SMTP bindings and settings were removed from the runtime. SendGrid remains
  separate from sign-in.
- Google verified and published the **workspaceAlberta** app branding. The client
  retains only the canonical `/oauth/google/callback` redirect; the temporary
  staging redirect was removed after browser verification.
- Real Google sign-in, MCP consent, PKCE exchange, authenticated identity,
  refresh rotation and replay rejection passed on the staging revision. The
  corporate Claude submission flow then connected successfully to production.
- All 14 production preflight checks passed, including all 26 tool titles in
  both supported locations. The final title patch passed 14 focused tests and
  the GitHub smoke/security checks. The prior complete local suite contained
  170 tests (162 passed, eight opt-in tests skipped); the eight live database
  tests passed separately.
- The approved Google sign-in button and public `/privacy`, `/support` and
  `/icon.svg` assets are deployed. The consent-page redesign is deferred at the
  owner's request; it shipped in the archival release above.
- Official MCP Inspector 2.8.0 exercised all 26 tools successfully against the
  public endpoint using the isolated review tenant. The sample profile and one
  watchlist entry remain available for reviewers. The E2B sandbox closed after
  the notice-text review. Evidence is in the local rollout output directory;
  no credential is stored in those reports.

### Reviewer access operations

The complimentary review tenant uses internal marker
`review_only_anthropic_20260926` in `wa_subscribers.stripe_customer_id`. This is
explicitly **not** a Stripe customer ID: no Stripe customer, subscription or
payment was created. Its non-deliverable sample email is
`anthropic-review@workspacealberta.invalid`. It contains a fictional company
profile and public tender data, separate from the owner's OAuth account.

Its legacy bearer key is in Secret Manager
`workspacealberta-anthropic-review-key:1`; only the hash is in the database.
It is not a Google credential and is not bound to the Cloud Run runtime. The
owner authorized sharing it with Anthropic, and the private test instructions
were verified after saving. The temporary plaintext handoff file was removed.
The key has no automatic expiry. Revoke it after review by cancelling only this
tenant in Supabase:

```sql
update public.wa_subscribers
set status = 'cancelled'
where stripe_customer_id = 'review_only_anthropic_20260926'
  and email = 'anthropic-review@workspacealberta.invalid';
```

Existing validation caches expire within five minutes. Disabling the Secret
Manager version alone does not revoke copies already supplied to reviewers.

### Earlier email-based staging record

The following records the superseded email experiment. Its provider issue is
not a blocker for the deployed Google sign-in flow.

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
- At that checkpoint, production remained on APC revision
  `workspacealberta-apc-e3b174942ae2`; the Google revision above now serves traffic.

Validation: 151 local tests passed, with eight integration tests skipped
by default. All eight opt-in tests passed separately, including the real Supabase
HTTP flow. GitHub smoke checks passed for the deployed code. The stale adapter
contract tests were repaired and added to CI. Syntax/import and whitespace
checks passed. The injection, replay,
concurrent-claim, and private-destination triggers no longer reproduce;
existing PKCE, refresh, anonymous tools, and legacy-key gating tests still pass.

Operational details and verification commands are in [OAuth deployment](oauth.md).
