# Public Endpoint Accessibility

How the hosted MCP endpoint stays easy to connect to, and the operator steps
that are not code changes.

## What the server now does (shipped in code)

- **Stateless StreamableHTTP with JSON responses.** Cloud Run routes each
  request to any instance, so in-memory MCP sessions intermittently failed with
  `400: Missing session ID` after scale events. The transport now runs
  `stateless=True, json_response=True`; every request is self-contained.
- **Relaxed Accept handling.** Clients that send only `Accept: application/json`
  used to get `406 Not Acceptable`. The `/mcp` adapter now widens the Accept
  header before handing off to the SDK.
- **CORS enabled.** Browser-based MCP clients (web inspectors, playgrounds)
  pass preflight; `mcp-session-id` and `mcp-protocol-version` are exposed.
- **Landing page at `/`.** Visitors who paste the bare host into a browser get
  connect instructions instead of a 404.
- **Public multi-user mode.** Set `WORKSPACEALBERTA_PUBLIC_MODE=1` on hosted
  deployments. This hides `set_business_profile` / `get_my_profile` (which
  share one file across all callers) and callers pass a per-request `profile`
  argument to `find_matching_opportunities`, `daily_bid_brief`,
  `find_opportunities`, and `find_alberta_opportunities` instead.

## Operator checklist (not code)

### 1. Set the public-mode env var on Cloud Run

```bash
gcloud run services update workspacealberta \
  --region northamerica-northeast1 \
  --update-env-vars WORKSPACEALBERTA_PUBLIC_MODE=1
```

### 2. Kill cold starts

First query after idle downloads the CanadaBuys CSV on top of the container
cold start, which reads as "the tool is broken" to a first-time user.

```bash
gcloud run services update workspacealberta \
  --region northamerica-northeast1 \
  --min-instances 1
```

### 3. Publish the npm bridge

`@warreandvavasour/workspace-alberta` is referenced in onboarding copy but not
yet on npm, so `npx -y @warreandvavasour/workspace-alberta` fails with 404 for
every stdio-only client. Follow the publishing checklist in
`packages/workspace-alberta-mcp/README.md`.

### 4. Use a trustworthy hostname

`elbowsupknivesout.warreandvavasour.com` is memorable but reads as suspicious
to cautious owners, and unrecognizable hostnames are more likely to be blocked
by managed corporate networks. Map a clean domain (for example
`mcp.workspacealberta.ca`) to the Cloud Run service and use it in all
onboarding copy, with the `*.run.app` URL as the fallback.

### 5. List the server in the MCP registry

`server.json` at the repo root is the manifest for
[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
Publishing makes the server discoverable inside MCP clients that browse the
registry:

```bash
brew install mcp-publisher   # or download from github.com/modelcontextprotocol/registry
mcp-publisher login github   # proves ownership of the HarleyCoops namespace path
mcp-publisher publish
```

Note: the manifest uses the `com.warreandvavasour/*` namespace, which requires
DNS or HTTP domain verification for `warreandvavasour.com`; alternatively
rename to `io.github.harleycoops/workspace-alberta` and GitHub login alone is
enough.

### 6. Optional next steps

- Claude Desktop extension bundle (`.mcpb`) for one-click desktop install.
- A short "connect in 60 seconds" page on the landing site per client
  (Claude Desktop, Cursor, Cline, VS Code, Zed), mirroring `/` on the service.
