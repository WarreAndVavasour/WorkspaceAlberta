# Connector readiness and paid access

OAuth lets someone connect their workspaceAlberta account to an MCP client,
approve access, and use the tools their subscription permits. Public procurement
search stays open. The same server can serve Claude, Claude Code, and other
compatible clients; future Astra integration needs its published requirements
and client tests before we claim compatibility.

## What changed and why it matters

| Change | Why it matters |
|---|---|
| Escaped sign-in and consent pages | A registered client name, login ID, or backend error cannot insert executable HTML into the sign-in page. |
| Database migrations `002` and `003` | Identity and OAuth grants survive restarts. Atomic claims and a locked email-code verifier prevent replay and lost attempt counts across Cloud Run instances. |
| Restricted client-metadata fetching | Client discovery cannot follow redirects to internal services or switch DNS destinations after validation. HTTPS hostname checks and response-size limits remain enforced. |
| Shared signing secret | Every instance verifies the same access tokens. The key is stored in Secret Manager, outside git. |
| SMTP with verified TLS | Users receive their own sign-in codes. Cloud Run rejects missing email configuration, debug codes, and in-memory OAuth storage. |

Supabase is the existing Toronto **database** in this implementation. It does
not send these custom login codes. Its default Auth mail service is also
[restricted to project-team recipients and unsuitable for production](https://supabase.com/docs/guides/auth/auth-smtp).
The selected sender is Twilio SendGrid: `smtp.sendgrid.net`, port `587`, STARTTLS,
username `apikey`, and a Mail Send API key as the password. The From address
must be verified in that account. See [SendGrid's SMTP setup](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/integrating-with-the-smtp-api).
Database and signing-key storage remain in Canada; SendGrid email processing
is a separate provider arrangement, not a Canada-only residency claim.

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

Complete email delivery and the staged Cloud Run rollout, then test discovery,
sign-in, approval/denial, refresh, anonymous search, paid access, and an inactive
subscriber through the public endpoint. Test each tool in Claude and confirm
tool titles and read/write annotations. Prepare a privacy policy, support
contact, icon, setup instructions, and a populated reviewer account, then
submit through [Anthropic's developer portal](https://claude.com/docs/connectors/building/submission).
OAuth is part of readiness; merging this change does not publish a listing.

The harness should use discovery, PKCE, refresh, and reconnect against this same
endpoint. It does not need a copy of the server's authentication or billing code.

## Rollout record — 2026-09-26

- Applied migrations `002` and `003` to the existing Toronto Supabase project,
  after a transaction rollback validation. Tested single-use grants and OTP
  concurrency against the real database; synthetic test rows were cleaned up.
- Created Secret Manager secret `workspacealberta-oauth-signing-key`, version
  `1`, replicated in Montréal; granted the existing Cloud Run runtime access.
- SMTP credential and verified sender setup is pending access to the existing
  SendGrid account. No OAuth production cutover has been performed yet.
- Production remains on APC revision `workspacealberta-apc-e3b174942ae2`.

Operational details and verification commands are in [OAuth deployment](oauth.md).
