# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorkspaceAlberta is a **workspace generator** for building personalized, high-context AI environments (primarily for **Claude**). It is specifically engineered to support Alberta's federal priority industries (**Steel, Lumber, Aluminum**) by connecting industry-specific business tools and **CanadaBuys** federal data to AI assistants via **Model Context Protocol (MCP)** servers.

The core workflow:

1. Business owner lists their tools in `owner-tools-list.md`.
2. Owner describes a primary business problem in `monthly-pain-point.md`.
3. Generator creates workspace configs (`.cursor/mcp.json`, `env/.env.example`, `docs/INTEGRATIONS.md`).
4. Industry-specific data pipelines (e.g., CanadaBuys) are activated to provide federal context.
5. User opens the environment in Cursor or Codespaces to solve their problem with an agentic AI assistant.

## Key Commands

### Generator (CLI)

```bash
python generator/generator.py <tool_id> [tool_id...]
```

Example:

```bash
python generator/generator.py google_drive slack github stripe
```

This generates three files:

- `.cursor/mcp.json` - MCP server configurations for Cursor
- `env/.env.example` - Template with required environment variables
- `docs/INTEGRATIONS.md` - Documentation table of selected integrations

### Data Pipelines (CanadaBuys)

```bash
python pipelines/canadabuys/pipeline.py --source open
```
Processes federal tender notices for Alberta and primary industries.

### Frontend (planned UI)

```bash
cd frontend
npm install
npm run dev    # Start Next.js dev server on http://localhost:3000
```

## Architecture

### Generator System ([generator/](generator/))

**Single Source of Truth: [generator/catalog.json](generator/catalog.json)**

- Contains 50 SMB tools organized by category.
- Each tool defines MCP configuration and required environment variables.

**Generator Utilities ([generator/generator.py](generator/generator.py)):**
- `build_mcp_json(selected_tools)` - Constructs Cursor's `.cursor/mcp.json` format.
- `write_workspace_files(root, selected_tools)` - Writes all three configuration files to disk.

### Industry Pipelines ([pipelines/](pipelines/))

- **CanadaBuys**: Integrated with the federal CKAN API to fetch, filter, and summarize government contracts for Steel, Lumber, and Aluminum sectors in Alberta.

### User Input Files

- **[owner-tools-list.md](owner-tools-list.md)**: Simple list of business tools/systems.
- **[monthly-pain-point.md](monthly-pain-point.md)**: Description of ONE business problem to solve.

### Cursor Rules ([.cursor/rules/small-business.mdc](.cursor/rules/small-business.mdc))

- Use clear, non-technical language.
- Prioritize simplicity and automation.
- **Always confirm before making changes to external services.**

## Technical Notes

- **MCP Types**: `node`/`python` (local), `http` (remote), `http_openapi` (wrapped OpenAPI).
- **Environment**: All sensitive keys are handled via `.env` files (gitignored).
- **Codespaces**: `generator/codespace_generator.py` generates `devcontainer.json` for one-click cloud deployment.

## Communication Guidelines

- Avoid jargon; explain technical terms like "MCP" using analogies (e.g., "universal translator").
- Focus on the "Problem" over the "Process" when helping business owners.
- Offer clear, step-by-step instructions for non-technical users.
