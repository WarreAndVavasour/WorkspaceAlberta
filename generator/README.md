# WorkspaceAlberta Generator Assets

This folder holds the catalog and helpers for generating per-business Cursor workspaces with only the MCP servers the user selects.

## Files
- `catalog.json` - single source of truth for 50 SMB tools with categories, MCP wiring, and env vars.
- `generator.py` - utilities to load the catalog, select tools, and emit `.cursor/mcp.json`, `env/.env.example`, and `docs/INTEGRATIONS.md`.

## Catalog conventions
- `integration_status`: `native` (known MCP server), `openapi` (uses published OpenAPI), `proxy` (expects your OpenAPI wrapper URL via `*_OPENAPI_URL`), `hosted` (remote MCP endpoint like Stripe).
- `http_openapi` entries with `openapi_url_env` must be paired with a working OpenAPI spec URL (usually from your own wrapper or gateway). That env var is included automatically in the `.env.example`.
- Env var names are unique across tools so the generator can dedupe.

## Generate a workspace config
```bash
# Example: generate configs for Google Drive, Slack, GitHub, Stripe
python -m generator.generator google_drive slack github stripe
```
- Outputs into the current working directory: `.cursor/mcp.json`, `env/.env.example`, `docs/INTEGRATIONS.md`.
- Override the OpenAPI wrapper command/args in code (see `DEFAULT_OPENAPI_WRAPPER_*`) or pass `BuildOptions` if you import the helpers.
- For `proxy` tools, fill the `*_OPENAPI_URL` values in your `.env` to point at your wrapper/gateway specs.

## Using the helpers programmatically
```python
from generator.generator import (
    build_env_example,
    build_integrations_md,
    build_mcp_json,
    load_catalog,
    select_tools,
)

catalog = load_catalog()
selection = select_tools(catalog, ["google_drive", "slack", "github", "stripe"])

mcp_json = build_mcp_json(selection)
env_example = build_env_example(selection)
integrations_md = build_integrations_md(selection)
```

Use `write_workspace_files(root, selection, options)` to emit the three files to disk.

## GitHub automation sketch
1. Collect `githubUsername`, `repoName`, and `selectedIds` from the UI.
2. `tools = select_tools(load_catalog(), selected_ids)`
3. Build content: `mcp.json`, `.env.example`, `INTEGRATIONS.md`, `README.md` stub.
4. Create repo from template (Octokit), add files in one commit, push, invite collaborator.
5. User clones, fills `env/.env`, and opens in Cursor.

## Next actions
- Wire the OpenAPI MCP wrapper you plan to ship (replace `your-openapi-mcp-wrapper` in `generator.py`).
- Decide default endpoints for `proxy` tools (e.g., local gateway vs. cloud host) and set the `*_OPENAPI_URL` values accordingly.
- Add UI copy that maps the catalog `description` + `category` into the selection list.

---

## Codespace Generator (NEW)

The `codespace_generator.py` extends the original generator to create complete GitHub Codespace configurations that business owners can launch with one click.

### What it generates

```
output-directory/
  .devcontainer/
    devcontainer.json    # Full Codespace configuration
    setup.sh             # Post-create setup script
  .vscode/
    mcp.json             # MCP server definitions for VS Code
  docs/
    WELCOME.md           # Personalized welcome guide
  problems/
    business-problem.md  # Business problem documentation
  README.md              # Quick start with Codespaces badge
```

### Usage

```bash
# Generate a complete Codespace-ready workspace
$env:BUSINESS_PROBLEM="I want to track customer payments and send follow-up emails automatically"; `
python -m generator.codespace_generator ./output "My Business Workspace" "John Doe" stripe google_calendar github
```

### Programmatic Usage

```python
from generator.codespace_generator import CodespaceConfig, write_codespace_files
from generator.generator import load_catalog, select_tools

catalog = load_catalog()
tools = select_tools(catalog, ["stripe", "google_calendar", "github"])

config = CodespaceConfig(
    workspace_name="My Business Workspace",
    business_problem="I want to track customer payments and send follow-up emails",
    owner_name="John Doe",
    tools=tools,
)

write_codespace_files("./output", config, "myorg/my-workspace-repo")
```


### Features

- **Pre-configured devcontainer.json** - Includes Node.js, Python, GitHub CLI, and recommended VS Code extensions
- **MCP servers auto-configured** - Based on selected tools from the catalog
- **Secrets management** - Lists required secrets with descriptions; prompts users in Codespaces
- **Welcome documentation** - Auto-opens when Codespace launches
- **One-click launch** - README includes Codespaces badge for instant access

### Integration with GitHub API

To create repositories programmatically with this configuration:

1. Generate the Codespace config files
2. Use GitHub API to create repo from template (or new repo)
3. Push generated files to the repository
4. Set repository/organization secrets via API
5. Share the Codespaces URL with the business owner

See `docs/codespaces-as-a-service-research.md` for the full architecture documentation.
