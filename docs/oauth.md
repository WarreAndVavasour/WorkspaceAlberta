# workspaceAlberta OAuth 2.1

This is the deploy checklist for the hosted MCP authorization server. The
server is listed for Claude as
`https://elbowsupknivesout.warreandvavasour.com/mcp`.

For a brief explanation of the changes, billing, and current rollout status,
see [Connector readiness](connector-readiness.md).

## Implemented behavior

workspaceAlberta is its own MCP-compliant authorization server on the same
Canadian origin as the MCP resource (Cloud Run, Montréal). Login is an email
one-time code. Tokens are audience-bound to the MCP URL. Stripe still owns
billing: Pro tools unlock only when the signed-in email matches an active
`wa_subscribers` row. Legacy `wa_live_` keys keep working.

Free tools stay anonymous. That is Anthropic **lazy authentication**:
`initialize`, `tools/list`, and free tools never 401. A Pro tool without a
token returns HTTP 401 with
`WWW-Authenticate: Bearer resource_metadata="..."`. Claude then shows Connect,
runs PKCE, and retries. A 200 JSON-RPC error does **not** start sign-in.

## Why this implementation

PR #32 put the OAuth endpoints and email-code login in the existing FastAPI
server, with persistent state in Toronto Supabase PostgreSQL. This follow-up
preserves that design and fixes the browser output and one-time-state boundaries.
[Supabase Auth also supports MCP OAuth](https://supabase.com/docs/guides/auth/oauth-server/mcp-authentication);
it is not the token issuer used by this code. Email delivery uses a separate
SMTP provider; Canadian database hosting does not imply Canadian email processing.

## Cloud Run configuration

Placeholders only in git. Set the real values in Cloud Run / Secret Manager.

| Variable | Required | Notes |
|---|---|---|
| `WA_PUBLIC_ORIGIN` | yes | `https://elbowsupknivesout.warreandvavasour.com` |
| `WA_PUBLIC_MCP_URL` | yes | `https://elbowsupknivesout.warreandvavasour.com/mcp` — must match the URL pasted into Claude |
| `WA_OAUTH_SIGNING_KEY` | yes | Long random string. Access tokens are HMAC-signed with this. Required for multi-instance Cloud Run |
| `WA_HOSTED` | yes | `1` — disables the shared anonymous `profile.json` |
| `WA_SMTP_HOST` | yes for real email | Selected provider: `smtp.sendgrid.net` |
| `WA_SMTP_PORT` | no | Default `587` |
| `WA_SMTP_USER` | if the SMTP host needs auth | SendGrid uses the literal `apikey` |
| `WA_SMTP_PASSWORD` | if the SMTP host needs auth | SendGrid API key with Mail Send permission; inject from Secret Manager |
| `WA_SMTP_FROM` | yes when SMTP is set | From-address users will see |
| `WA_SMTP_STARTTLS` | no | Default `1`; TLS certificates are verified |
| `WA_OAUTH_DEV_SHOW_CODE` | local only | `1` prints the code on a local login page. Cloud Run startup rejects this setting |
| `WA_OAUTH_STORE` | hosted | Set `supabase`. Cloud Run startup rejects memory storage |
| `WA_OAUTH_EXTRA_RESOURCES` | no | Comma-separated extra `resource` values for local inspector testing |

Existing vars stay required for Pro: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`STRIPE_WEBHOOK_SECRET`.

## Supabase migration

In the Toronto project SQL editor, apply:

1. `pipelines/migrations/001_create_wa_subscribers.sql` (if not already applied)
2. `pipelines/migrations/002_oauth_identity.sql`
3. `pipelines/migrations/003_oauth_atomic_login.sql`

`002` creates `wa_users`, `wa_user_data`, and the OAuth client / code / refresh /
login tables, plus `wa_subscribers(lower(email))`. All tables are service-role
only.

`003` installs a service-role-only function that locks the challenge row while
checking the email code, counting failed attempts, and consuming a successful
login. Authorization codes, consent, and refresh tokens use conditional database
updates so only one concurrent request can consume them. The in-memory store
enforces the same transitions for local development.

Cloud Run startup requires a signing key of at least 32 characters, Supabase,
SMTP host/from address, and STARTTLS. Store the random signing key and SMTP
password in Secret Manager and bind explicit versions with `--update-secrets`;
do not replace the service's other secret mappings. Never put credentials in git.

After checkout, the webhook still writes `wa_subscribers.email`. Login looks
that row up by email (case-insensitive). Active `status` unlocks Pro.

## Cloudflare

Anthropic's connectors egress from `160.79.104.0/21`. The Worker in front of
`elbowsupknivesout.warreandvavasour.com` must not challenge or block:

- `/.well-known/oauth-protected-resource`
- `/.well-known/oauth-protected-resource/mcp`
- `/.well-known/oauth-authorization-server`
- `/authorize` (browser login + consent)
- `/token`
- `/register`
- `POST /mcp`

Turn off bot-fight / WAF rules that 403 those paths for that IP range. A
blocked metadata or token call shows up in Claude as "Couldn't reach the MCP
server" or "Authorization with the MCP server failed".

## End-to-end test after deploy

### 1. Discovery (no sign-in)

```bash
curl -s https://elbowsupknivesout.warreandvavasour.com/.well-known/oauth-protected-resource
curl -s https://elbowsupknivesout.warreandvavasour.com/.well-known/oauth-protected-resource/mcp
curl -s https://elbowsupknivesout.warreandvavasour.com/.well-known/oauth-authorization-server
```

`resource` must be exactly `https://elbowsupknivesout.warreandvavasour.com/mcp`.
The authorization-server document must list `/authorize`, `/token`, `/register`,
`code_challenge_methods_supported: ["S256"]`,
`client_id_metadata_document_supported: true`, and `"none"` in
`token_endpoint_auth_methods_supported`.

### 2. Lazy 401 vs free tools

```bash
curl -si https://elbowsupknivesout.warreandvavasour.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

curl -si https://elbowsupknivesout.warreandvavasour.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_watchlist","arguments":{}}}'
```

`tools/list` is 200. `list_watchlist` is 401 with `WWW-Authenticate` pointing
at the protected-resource metadata URL.

### 3. Claude (or MCP Inspector)

1. Claude: Customize → Connectors → Add custom connector → paste
   `https://elbowsupknivesout.warreandvavasour.com/mcp`.
2. Ask for a CanadaBuys search or daily brief. No sign-in prompt.
3. Ask to list the watchlist or score a bid. The inline Connect card appears.
4. Sign in with the Stripe checkout email. Approve the consent screen
   (it names the redirect host).
5. Claude retries. Pro works only while `wa_subscribers.status` is `active`.
6. Claude Code also needs loopback redirects (`http://localhost` /
   `127.0.0.1`, any port). Those are already allowlisted.

MCP Inspector: point it at the same `/mcp` URL, start OAuth, and complete
the email-code + consent pages. A Cloud Run staging revision also needs real
SMTP; debug codes are permitted only in local development.

### 4. Legacy key

```bash
curl -s -H "Authorization: Bearer wa_live_..." \
  https://elbowsupknivesout.warreandvavasour.com/me
```

Still returns plan, email, and `auth_type: api_key`.

## Local tests

```bash
python -m pip install -r requirements.txt
python -m unittest tests.test_oauth tests.test_oauth_security tests.test_gate_and_billing tests.test_procurement_http_app tests.test_canadabuys_mcp_smoke
```

To exercise real PostgreSQL/PostgREST concurrency and the HTTP login flow, set `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY` securely, then run
`WA_OAUTH_TEST_SUPABASE=1 python -m unittest tests.test_oauth_security.LiveSupabaseTest tests.test_oauth_security.LiveOAuthHttpTest`.
These opt-in suites create and remove their own synthetic OAuth rows, send no
email, and do not create subscriptions or modify customer profiles. The HTTP
test captures the mail call in-process, uses an ephemeral signing key, and checks
consent, PKCE, authorization-code replay, refresh rotation, and refresh replay.
It does not validate the deployed mail provider.

## Deployment checks while email is deferred

Use a tagged revision with zero production traffic. Database migrations and
secret bindings can be verified independently of email delivery; keep
`WA_OAUTH_DEV_SHOW_CODE=0` on every hosted revision.

```bash
python scripts/verify_oauth_readiness.py \
  --url https://oauth-ready---workspacealberta-b7gk5pch5q-nn.a.run.app \
  --resource https://elbowsupknivesout.warreandvavasour.com/mcp \
  --client-metadata-url https://claude.ai/oauth/claude-code-client-metadata \
  --output output/oauth-rollout/staging-readiness.json
```

This preflight checks both discovery documents, MCP initialization and tool
metadata, anonymous access, missing/invalid-token challenges, invalid refresh
responses, and the CIMD authorization page. It sends no codes, creates no
accounts or clients, and performs no paid tool work. Its report explicitly marks
email delivery and customer sign-in as untested.

The tagged revision advertises the canonical production issuer and resource.
It is a preflight target, not a separate OAuth issuer for a customer connector.
After email delivery is verified and traffic is promoted, rerun the preflight
against the public domain and complete a real client sign-in. Signed-in users
without an active subscription receive an MCP tool error without restarting
OAuth; anonymous callers still receive an HTTP 401 challenge for protected tools.
