# Custom MCP Servers

Custom Model Context Protocol (MCP) servers for Alberta small business workflows.

## Available Servers

### local_contacts

Read customer and supplier contacts from local Excel/CSV spreadsheets.

```bash
# Run the server
python -m mcp_servers.local_contacts.server

# Environment variables
CONTACTS_FOLDER=~/Documents/Contacts  # Default location
```

**Tools:**
- `list_contact_files` - Find all spreadsheets in the contacts folder
- `get_contact_columns` - Get column structure of a spreadsheet
- `search_contacts` - Search for contacts by name, company, email, etc.
- `get_all_contacts` - Get all contacts from a specific file

### canadabuys

Search federal government procurement opportunities. Wraps the existing CanadaBuys pipeline.

```bash
# Run the server
python -m mcp_servers.canadabuys.server
```

**Tools:**
- `search_tenders` - Search for tenders by industry and region
- `get_tender_details` - Get full details for a specific tender
- `get_pipeline_summary` - Get statistics from the last pipeline run
- `run_pipeline` - Fetch fresh data from CanadaBuys
- `list_industries` - Show available industry filters

## Installation

```bash
# Install dependencies
pip install mcp pandas openpyxl

# From the WorkspaceAlberta root directory
python -m mcp_servers.local_contacts.server
```

## Adding to MCP Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "local-contacts": {
      "command": "python",
      "args": ["-m", "mcp_servers.local_contacts.server"],
      "env": {
        "CONTACTS_FOLDER": "~/Documents/Contacts"
      }
    },
    "canadabuys": {
      "command": "python",
      "args": ["-m", "mcp_servers.canadabuys.server"]
    }
  }
}
```

## Development

### Creating a New MCP Server

1. Create directory: `mcp_servers/<server_name>/`
2. Add `__init__.py` with description
3. Add `server.py` implementing the MCP protocol
4. Register in `generator/catalog.json`
5. Add to relevant profiles in `generator/profiles.py`

### MCP Server Template

```python
#!/usr/bin/env python3
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import asyncio

server = Server("my-server")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="my_tool",
            description="Description of what this tool does",
            inputSchema={
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "my_tool":
        result = do_something(arguments["param"])
        return [TextContent(type="text", text=json.dumps(result))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```
