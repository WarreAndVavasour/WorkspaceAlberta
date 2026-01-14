# E2B Sandbox Templates

This directory contains tools for building E2B sandbox templates with pre-configured MCP servers for different industry profiles.

## Overview

Each template is a Docker image that includes:
- Claude Code CLI
- MCP server configurations for the profile's tools
- Python and Node.js dependencies
- Setup scripts for the sandbox environment

## Quick Start

```bash
# List available profiles
python -m e2b.build_templates list

# Build all templates
python -m e2b.build_templates build-all

# Build a specific profile
python -m e2b.build_templates build steel_fabrication
```

## Deploying Templates to E2B

After generating template files:

```bash
# Install E2B CLI
npm install -g @e2b/cli

# Login to E2B
e2b login

# Build and deploy a template
cd e2b/templates/steel_fabrication
e2b template build

# The template ID will be printed - save it!
```

## Template Structure

Each profile generates:

```
e2b/templates/<profile>/
├── .mcp.json       # MCP server configuration
├── Dockerfile      # E2B template image
├── e2b.toml        # E2B configuration
└── setup.sh        # Environment setup script
```

## Using Templates with Claude Agent SDK

Once templates are deployed, use them to spawn specialized child agents:

```python
from e2b.orchestrator import spawn_child_agent

result = spawn_child_agent(
    profile="steel_fabrication",
    task="Find CanadaBuys tenders for steel fabrication",
)

print(result["result"])
```


## Available Profiles

| Profile | Description | Key Tools |
|---------|-------------|-----------|
| `foundation` | Core tools for any SMB | Filesystem, Gmail, Calendar, Web Search |
| `steel_fabrication` | Steel shops bidding on government contracts | CanadaBuys, Bid Calculator, QuickBooks |
| `lumber_mill` | Lumber and wood products | CanadaBuys, Inventory Tracker |
| `trades_contractor` | Electricians, plumbers, HVAC | Jobber, Wave Accounting |
| `general_contractor` | Construction project management | CanadaBuys, Bid Calculator |
| `metal_fabrication` | Machining and metal work | CanadaBuys, Inventory Tracker |
| `equipment_rental` | Rental and sales | Inventory Tracker, Jobber |
| `professional_services` | Consultants, accountants | Calendly, QuickBooks |

## Environment Variables

Templates expect these environment variables at runtime:

- `ANTHROPIC_API_KEY` - Required for Claude Code
- `E2B_API_KEY` - Required for spawning child sandboxes
- Profile-specific variables (see `generator/profiles.py`)
