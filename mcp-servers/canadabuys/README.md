# CanadaBuys MCP Server

Search Canadian federal government contracts via AI assistant.

## What This Does

Connects your AI to [CanadaBuys](https://canadabuys.canada.ca/) - the Canadian federal government's procurement database. 863+ active tender opportunities.

## Installation

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "canadabuys": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

### Claude Desktop

Add to Claude config:

```json
{
  "mcpServers": {
    "canadabuys": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `search_contracts` | Search by keywords, province |
| `get_contract_details` | Full details by reference number |
| `list_upcoming_deadlines` | Contracts closing soon |
| `summarize_contracts` | Overview of available contracts |
| `refresh_data` | Pull latest from CanadaBuys |

## Example Queries

Ask your AI:

- "Search for construction contracts"
- "Find IT contracts in Ontario"
- "What's closing in the next 7 days?"
- "Get details on contract PW-24-00912345"
- "Refresh the contract data"

## Configuration

```bash
# Custom data directory (default: ~/.canadabuys/)
export CANADABUYS_DATA_DIR=/path/to/data
```

## Data Source

- **URL:** `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`
- **Updated:** Daily by Government of Canada
- **Format:** CSV with 40+ fields per contract

## Requirements

- Python 3.10+
- `mcp` package (`pip install mcp`)

## License

MIT
