# WorkspaceAlberta Generator Assets

This folder holds the catalog and helpers for generating per-business Cursor workspaces with only the MCP servers the user selects.

## Files
- `catalog.json` - single source of truth for 50 SMB tools with categories, MCP wiring, and env vars.
- `generator.ts` - utilities to load the catalog, select tools, and emit `.cursor/mcp.json`, `env/.env.example`, and `docs/INTEGRATIONS.md`.

## Catalog conventions
- `integration_status`: `native` (known MCP server), `openapi` (uses published OpenAPI), `proxy` (expects your OpenAPI wrapper URL via `*_OPENAPI_URL`), `hosted` (remote MCP endpoint like Stripe).
- `http_openapi` entries with `openapi_url_env` must be paired with a working OpenAPI spec URL (usually from your own wrapper or gateway). That env var is included automatically in the `.env.example`.
- Env var names are unique across tools so the generator can dedupe.

## Generate a workspace config
```bash
# Example: generate configs for Google Drive, Slack, GitHub, Stripe
npx ts-node generator/generator.ts google_drive slack github stripe
```
- Outputs into the current working directory: `.cursor/mcp.json`, `env/.env.example`, `docs/INTEGRATIONS.md`.
- Override the OpenAPI wrapper command/args in code (see `DEFAULT_OPENAPI_WRAPPER_*`) or pass `BuildOptions` if you import the helpers.
- For `proxy` tools, fill the `*_OPENAPI_URL` values in your `.env` to point at your wrapper/gateway specs.

## Using the helpers programmatically
```ts
import { loadCatalog, selectTools, buildMcpJson, buildEnvExample, buildIntegrationsMd } from "./generator";

const catalog = loadCatalog();
const selection = selectTools(catalog, ["google_drive", "slack", "github", "stripe"]);

const mcpJson = buildMcpJson(selection);
const envExample = buildEnvExample(selection);
const integrationsMd = buildIntegrationsMd(selection);
```
Use `writeWorkspaceFiles(root, selection, options)` to emit the three files to disk.

## GitHub automation sketch
1. Collect `githubUsername`, `repoName`, and `selectedIds` from the UI.
2. `const tools = selectTools(loadCatalog(), selectedIds);`
3. Build content: `mcp.json`, `.env.example`, `INTEGRATIONS.md`, `README.md` stub.
4. Create repo from template (Octokit), add files in one commit, push, invite collaborator.
5. User clones, fills `env/.env`, and opens in Cursor.

## Next actions
- Wire the OpenAPI MCP wrapper you plan to ship (replace `your-openapi-mcp-wrapper` in `generator.ts`).
- Decide default endpoints for `proxy` tools (e.g., local gateway vs. cloud host) and set the `*_OPENAPI_URL` values accordingly.
- Add UI copy that maps the catalog `description` + `category` into the selection list.
