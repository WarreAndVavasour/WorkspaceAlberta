# Public Endpoint Accessibility

How the hosted MCP endpoint stays easy to connect to, and the operator steps
that are not code changes.

## What the server does (shipped in code)

- **Stateless StreamableHTTP with JSON responses.** Cloud Run routes each
  request to any instance, so in-memory MCP sessions intermittently failed
  with `400: Missing session ID` after scale events. The transport now runs
  `stateless=True, json_response=True`; every request is self-contained. The
  Pro gate is unaffected: the `Authorization` header is read per request.
- **Relaxed Accept handling.** Clients that send only `Accept:
  application/json` used to get `406 Not Acceptable`. The `/mcp` adapter now
  widens the Accept header before handing off to the SDK.
- **Fast 405 on `GET /mcp`.** The stateless transport never answers GET, which
  left browsers and probes hanging; the adapter fails fast with guidance.
- **CORS enabled.** Browser-based MCP clients (web inspectors, playgrounds)
  pass preflight; `mcp-session-id` and `mcp-protocol-version` are exposed.
- **Landing page at `/`.** Visitors who paste the bare host into a browser get
  connect instructions (including the Pro Bearer-key note) instead of a 404.
- **Inline per-request profiles.** Subscribers get tenant-scoped saved
  profiles via the key-hash tenancy in `procurement_core/storage.py`.
  Anonymous callers on the shared endpoint would otherwise share one
  file-backed profile, so every profile-consuming tool also accepts an inline
  `profile` argument (company_name, location, description, optional
  capabilities/industries) that overrides the saved one for that call.

## Operator checklist (not code)

### 1. Kill cold starts

First query after idle downloads the CanadaBuys CSV on top of the container
cold start, which reads as "the tool is broken" to a first-time user.

```bash
gcloud run services update workspacealberta \
  --region northamerica-northeast1 \
  --min-instances 1
```

### 2. Publish the npm bridge

`@warreandvavasour/workspace-alberta` is referenced in onboarding copy but not
yet on npm, so `npx -y @warreandvavasour/workspace-alberta` fails with 404 for
every stdio-only client. `.github/workflows/publish-npm.yml` can publish it
once the npm token secret is configured; see the checklist in
`packages/workspace-alberta-mcp/README.md`.

### 3. Use a trustworthy hostname

`elbowsupknivesout.warreandvavasour.com` is memorable but reads as suspicious
to cautious owners, and unrecognizable hostnames are more likely to be blocked
by managed corporate networks. Map a clean domain (for example
`mcp.workspacealberta.ca`) to the Cloud Run service and use it in all
onboarding copy, with the `*.run.app` URL as the fallback.

### 4. List the server in the MCP registry

`server.json` at the repo root is the manifest for
[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io).
Publishing makes the server discoverable inside MCP clients that browse the
registry:

```bash
brew install mcp-publisher   # or download from github.com/modelcontextprotocol/registry
mcp-publisher login github   # proves ownership of the namespace
mcp-publisher publish
```

Note: the manifest uses the `com.warreandvavasour/*` namespace, which requires
DNS or HTTP domain verification for `warreandvavasour.com`; alternatively
rename to `io.github.harleycoops/workspace-alberta` and GitHub login alone is
enough.

### 5. Optional next steps

- Claude Desktop extension bundle (`.mcpb`) for one-click desktop install.
- A short "connect in 60 seconds" page per client (Claude Desktop, Cursor,
  Cline, VS Code, Zed), mirroring the landing page at `/` on the service.
