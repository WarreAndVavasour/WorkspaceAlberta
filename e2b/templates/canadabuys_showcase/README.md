# CanadaBuys Showcase - E2B Template

A deployable E2B sandbox template featuring the CanadaBuys MCP server for searching Canadian federal government contracts via AI assistant.

## Quick Deploy

```bash
# 1. Install E2B CLI
npm install -g @e2b/cli

# 2. Login to E2B
e2b login

# 3. Build and deploy the template
cd e2b/templates/canadabuys_showcase
e2b template build

# 4. Save the template ID that's returned!
```

## What's Included

### MCP Servers
- **canadabuys** - Search 800+ federal government contracts
- **filesystem** - Read/write files in /workspace

### CanadaBuys Tools
| Tool | Description |
|------|-------------|
| `search_contracts` | Search by keywords, province |
| `get_contract_details` | Full details by reference number |
| `list_upcoming_deadlines` | Contracts closing within N days |
| `summarize_contracts` | Overview of available contracts |
| `refresh_data` | Pull latest from CanadaBuys |
| `set_business_profile` | Save your business for smart matching |
| `find_opportunities` | Find contracts that match your profile |
| `get_my_profile` | View current business profile |

## Usage After Deployment

Once deployed, use the template ID to spawn sandboxes:

```python
from e2b import Sandbox

# Replace with your actual template ID
sandbox = Sandbox.create(template="your-template-id")

# Run Claude Code with a task
result = sandbox.commands.run(
    'claude -p "Search for construction contracts in Alberta"',
    timeout=120,
)

print(result.stdout)
sandbox.close()
```

## Environment Variables

At runtime, you'll need:
- `ANTHROPIC_API_KEY` - Required for Claude Code

## Resources

- 2 CPU cores
- 4GB RAM
- Auto-cleanup after timeout
