# WorkspaceAlberta MCP

Stdio bridge for the hosted WorkspaceAlberta procurement MCP endpoint.

This package is for MCP clients that expect a local `command` transport. It starts `mcp-remote` and connects it to the hosted WorkspaceAlberta StreamableHTTP endpoint.

## MCP client config

```json
{
  "mcpServers": {
    "workspacealberta": {
      "command": "npx",
      "args": ["-y", "@warreandvavasour/workspace-alberta"]
    }
  }
}
```

No local Cohere key is required for the hosted endpoint. Model-backed tender analysis runs server-side when available.

## Override the endpoint

```bash
WORKSPACEALBERTA_MCP_URL=http://127.0.0.1:8000/mcp npx -y @warreandvavasour/workspace-alberta
```

Or pass a URL as the first argument:

```bash
npx -y @warreandvavasour/workspace-alberta http://127.0.0.1:8000/mcp
```

## Native HTTP clients

If your MCP client supports StreamableHTTP directly, use the hosted endpoint without this package:

```text
https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp
```
