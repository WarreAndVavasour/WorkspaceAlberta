# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorkspaceAlberta is a **workspace generator** for building personalized Cursor IDE environments. It connects business tools to AI assistants via MCP (Model Context Protocol) servers, enabling automated workflows based on the specific tools a business uses.

The core workflow:

1. Business owner lists their tools in `owner-tools-list.md`
2. Owner describes one problem to solve in `monthly-pain-point.md`
3. Generator creates workspace configs (`.cursor/mcp.json`, `env/.env.example`, `docs/INTEGRATIONS.md`)
4. Owner fills in API keys in `.env`
5. Opens workspace in Cursor to build solutions

## Key Commands

### Generator (CLI)

```bash
python -m generator.generator <tool_id> [tool_id...]
```

Example:

```bash
python -m generator.generator google_drive slack github stripe
```

This generates three files:

- `.cursor/mcp.json` - MCP server configurations for Cursor
- `env/.env.example` - Template with required environment variables
- `docs/INTEGRATIONS.md` - Documentation table of selected integrations

### Frontend (planned UI)

```bash
cd frontend
pip install -r requirements.txt
python app.py  # Start Flask dev server on http://localhost:5000
```

The frontend is a lightweight Flask app that guides tool selection and previews the generator command.

## Architecture

### Generator System ([generator/](generator/))

**Single Source of Truth: [generator/catalog.json](generator/catalog.json)**

- Contains 50 SMB tools organized by category (Storage/Productivity, Dev/Collaboration/Project, CRM/Sales/Support, Marketing/Content/Web, Finance/Ops/Data)
- Each tool defines: display name, category, description, integration status, and MCP configuration
- Env var names are unique across all tools (allows deduplication)

**Integration Statuses:**

- `native` - Known MCP server with published npm package (e.g., `mcp-server-google-drive`)
- `openapi` - Uses publicly available OpenAPI spec URL
- `proxy` - Requires custom OpenAPI wrapper; expects `*_OPENAPI_URL` env var pointing to your wrapper
- `hosted` - Remote MCP endpoint (e.g., Stripe's hosted server at `https://mcp.stripe.com`)

**Generator Utilities ([generator/generator.py](generator/generator.py)):**

- `load_catalog()` - Loads and parses catalog.json
- `select_tools(catalog, selected_ids)` - Validates and filters tools by ID
- `build_mcp_json(selected_tools, options)` - Constructs Cursor's `.cursor/mcp.json` format
- `build_env_example(selected_tools)` - Generates `.env.example` with all required vars (deduplicated)
- `build_integrations_md(selected_tools)` - Creates markdown documentation table
- `write_workspace_files(root, selected_tools, options)` - Writes all three files to disk

**MCP Server Types:**

- `node`/`python` - Local executables with command + args
- `http` - Remote HTTP endpoint with URL
- `http_openapi` - OpenAPI spec wrapped by a generic MCP server (uses `OPENAPI_SPEC_URL` env var)

For `http_openapi` tools, the generator injects wrapper command/args:

- Default: `npx -y your-openapi-mcp-wrapper` (placeholder - see generator.py)
- Override via `BuildOptions.openapiWrapperCommand` and `openapiWrapperArgs`

### User Input Files

**[owner-tools-list.md](owner-tools-list.md)**
Simple list of all tools/systems the business uses. No structure required - just names.

**[monthly-pain-point.md](monthly-pain-point.md)**
Description of ONE business problem to solve, stated in plain language. Not workflow steps or technical details - just the problem itself.

### Cursor Rules ([.cursor/rules/small-business.mdc](.cursor/rules/small-business.mdc))

Communication style for small business owners:

- Use clear, non-technical language
- Explain acronyms on first use
- Prioritize simplicity over advanced features
- Suggest automations for repetitive tasks
- **Always confirm before making changes to external services**
- Always preview changes and explain potential impacts

## Environment Variables

The `.env.example` file is a template. Users copy it to `.env` (gitignored) and fill in their API keys.

For `proxy` integration tools, fill the `*_OPENAPI_URL` values to point at your OpenAPI wrapper/gateway specs.

## Important Notes

### When Adding New Tools to Catalog

1. Assign a unique `id` (snake_case)
2. Choose appropriate `category` (existing or new)
3. Set `integration_status` correctly:
   - Use `native` only if a published MCP server exists
   - Use `openapi` if there's a stable public OpenAPI spec URL
   - Use `proxy` if it needs a custom wrapper (add `openapi_url_env`)
   - Use `hosted` for remote HTTP MCP endpoints
4. Ensure all `env_vars` have unique names across the catalog
5. For `http_openapi` type: either provide `openapi_url` OR `openapi_url_env` (not both)

### Generator Output Locations

The generator writes to:

- `.cursor/mcp.json` - Cursor IDE's MCP configuration
- `env/.env.example` - Environment variable template
- `docs/INTEGRATIONS.md` - Generated documentation

These are relative to the `root` parameter passed to `writeWorkspaceFiles()` (defaults to `process.cwd()` when running CLI).

### OpenAPI Wrapper

The default OpenAPI wrapper command (`your-openapi-mcp-wrapper`) is a placeholder. Before production use:

1. Implement or select an actual OpenAPI-to-MCP wrapper server
2. Update `DEFAULT_OPENAPI_WRAPPER_COMMAND` and `DEFAULT_OPENAPI_WRAPPER_ARGS` in [generator/generator.py](generator/generator.py)
3. Or pass custom values via `BuildOptions` when calling `buildMcpJson()`

## File Structure

```text
WorkspaceAlberta/
  .cursor/
    rules/
      small-business.mdc      # Cursor behavior rules
  docs/
    getting-started.md        # Setup instructions
    WorkspaceAlberta.md       # Project task documentation
    INTEGRATIONS.md           # Generated by generator (if run)
  env/
    .env.example              # Generated by generator (if run)
  frontend/                   # Flask web UI
    app.py                    # Flask app entrypoint
    templates/                # Jinja templates
    static/                   # CSS and assets
    requirements.txt          # UI dependencies
    README.md                 # UI usage
  generator/
    catalog.json              # 50-tool catalog (single source of truth)
    generator.py              # Core generation utilities
    codespace_generator.py    # Codespace generator
    profiles.py               # Profile helpers
    README.md                 # Generator documentation
  .env.example                # Static example env file
  mcp-config.template.json    # Example MCP configuration
  owner-tools-list.md         # User input: tools they use
  monthly-pain-point.md       # User input: problem to solve
  README.md                   # Main documentation
```


## Communication Guidelines

When working with small business owners (per Cursor rules):

- Avoid jargon; explain technical terms when necessary
- Break down complex changes into clear steps
- Offer context for why actions are recommended
- Create backups when modifying important files
- Ask for confirmation before making changes to external services
