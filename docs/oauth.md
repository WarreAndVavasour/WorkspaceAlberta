# workspaceAlberta OAuth 2.1

This is the deploy checklist for the hosted MCP authorization server. The
server is listed for Claude as
`https://elbowsupknivesout.warreandvavasour.com/mcp`.

Do not merge this as a live cutover note: apply the migration and env vars on
Cloud Run only when Christian is ready to deploy.

## What shipped

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

Supabase Auth is a good identity store, not an MCP authorization server. It
does not speak RFC 9728, RFC 7591, RFC 8707 resource indicators, CIMD, or
Claude's redirect rules. Putting our own OAuth 2.1 layer in the FastAPI app
and keeping state in the Toronto Supabase project stays on the existing
Python stack, keeps data in Canada, and matches the connector-directory
contract.

Google sign-in was not added. Google's authorization servers are US-hosted.

## Env vars Christian must set on Cloud Run

Placeholders only in git. Set the real values in Cloud Run / Secret Manager.

| Variable | Required | Notes |
|---|---|---|
| `WA_PUBLIC_ORIGIN` | yes | `https://elbowsupknivesout.warreandvavasour.com` |
| `WA_PUBLIC_MCP_URL` | yes | `https://elbowsupknivesout.warreandvavasour.com/mcp` — must match the URL pasted into Claude |
| `WA_OAUTH_SIGNING_KEY` | yes | Long random string. Access tokens are HMAC-signed with this. Required for multi-instance Cloud Run |
| `WA_HOSTED` | yes | `1` — disables the shared anonymous `profile.json` |
| `WA_SMTP_HOST` | yes for real email | Canadian SMTP if possible |
| `WA_SMTP_PORT` | no | Default `587` |
| `WA_SMTP_USER` | if the SMTP host needs auth | |
| `WA_SMTP_PASSWORD` | if the SMTP host needs auth | Secret |
| `WA_SMTP_FROM` | yes when SMTP is set | From-address users will see |
| `WA_SMTP_STARTTLS` | no | Default `1` |
| `WA_OAUTH_DEV_SHOW_CODE` | staging only | `1` prints the one-time code on the login page. Leave off in production |
| `WA_OAUTH_STORE` | no | Default: Supabase when configured, memory otherwise. Production must use Supabase |
| `WA_OAUTH_EXTRA_RESOURCES` | no | Comma-separated extra `resource` values for local inspector testing |

Existing vars stay required for Pro: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`STRIPE_WEBHOOK_SECRET`.

## Supabase migration

In the Toronto project SQL editor, apply:

1. `pipelines/migrations/001_create_wa_subscribers.sql` (if not already applied)
2. `pipelines/migrations/002_oauth_identity.sql`

`002` creates `wa_users`, `wa_user_data`, and the OAuth client / code / refresh /
login tables, plus `wa_subscribers(lower(email))`. All tables are service-role
only.

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
the email-code + consent pages. Use `WA_OAUTH_DEV_SHOW_CODE=1` only on a
staging revision if email is not wired yet.

### 4. Legacy key

```bash
curl -s -H "Authorization: Bearer wa_live_..." \
  https://elbowsupknivesout.warreandvavasour.com/me
```

Still returns plan, email, and `auth_type: api_key`.

## Local tests

```bash
python -m pip install -r requirements.txt
python -m unittest tests.test_oauth tests.test_gate_and_billing tests.test_procurement_http_app tests.test_canadabuys_mcp_smoke
```
