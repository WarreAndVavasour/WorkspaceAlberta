# WorkspaceAlberta - Cursor Workspace Templates for Cohorts

**Task ID:** T-2025-12-001  
**Status:** Active  
**Created:** 2025-12-08  
**Priority:** High  

---

## Problem Statement

Create shareable Cursor workspace configurations for specific user cohorts (e.g., small business owners) such that any GitHub clone of the repo would open with the same connections, MCP settings, layout, and customizations - but without exposing API keys.

## Goals

1. **Workspace Template System** - Use Cursor API/SDK to build, design, and set up workspaces
2. **GitHub-Shareable** - Any clone of the repo inherits the workspace configuration
3. **Secure Key Management** - MCP connections work without exposing API keys (env vars, secret manager, or similar)
4. **Cohort Customization** - Custom layout, settings, colors per target audience

## Target Cohort: Small Business Owners

Initial focus cohort with specific needs:
- Simplified MCP connections (calendar, email, basic automation)
- Clean, non-technical layout
- Pre-configured tools for common business tasks

## Technical Research Required

### Cursor Configuration Files
- [ ] `.cursor/` directory structure and capabilities
- [ ] `.cursor/rules/` for custom rules (already using)
- [ ] Workspace settings persistence
- [ ] MCP server configuration portability

### Key Management Options
- [ ] `.env` + `.env.example` pattern (current approach)
- [ ] Reference environment variables in MCP configs
- [ ] Google Secret Manager integration
- [ ] Azure Key Vault / AWS Secrets Manager alternatives

### Sharing Mechanisms
- [ ] GitHub template repositories
- [ ] Cursor workspace export/import (if available)
- [ ] devcontainer.json integration

## Current Understanding

Cursor uses several configuration locations:
1. **Global Settings**: `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/`
2. **Workspace Rules**: `.cursor/rules/` in repo root
3. **MCP Settings**: `cline_mcp_settings.json` (global or per-workspace)

## Architecture Sketch

```
WorkspaceAlberta/
├── .cursor/
│   └── rules/
│       └── small-business.mdc     # Cohort-specific rules
├── .env.example                    # Template for required keys
├── mcp-config.template.json        # MCP config with ${VAR} placeholders
├── setup.ps1 / setup.sh           # One-click setup script
├── README.md                       # Setup instructions
└── docs/
    └── getting-started.md
```

## Next Steps

1. Research Cursor's workspace configuration API/capabilities
2. Prototype a minimal shareable workspace config
3. Test the env-var approach for MCP key injection
4. Document the setup process for non-technical users

## References

- [Cursor Documentation](https://cursor.sh/docs)
- [MCP Server Configuration](https://modelcontextprotocol.io/)
- Current Daily repo `.cursor/` setup as reference
- **GitHub Repository**: https://github.com/HarleyCoops/WorkspaceAlberta

---

## Log

### 2025-12-08
- Project created and registered in task pipeline
- Initial requirements documented
- Task T-2025-12-001 created
- GitHub repo created: https://github.com/HarleyCoops/WorkspaceAlberta
- Initial files pushed: README, .env.example, .gitignore, small-business.mdc rules, docs, mcp-config template

### 2025-12-23
- Built CanadaBuys MVP pipeline (CKAN + CanadaBuys CSV feeds)
- Added Alberta + Steel/Lumber/Aluminum UNSPSC filtering and keyword matching
- Generated per-tender markdown summaries with supporting document links
- Added attachment checks and download sampling for public documents
