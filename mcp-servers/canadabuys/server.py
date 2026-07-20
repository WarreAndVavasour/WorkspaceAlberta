#!/usr/bin/env python3
"""Stdio MCP adapter for the shared procurement core.

This is the local-first entry point: Claude Desktop, Cursor, OpenCode, and
any stdio-capable MCP client launch this script directly (see
``.mcp.json`` / ``mcp.json.example``). It owns no procurement logic — it
adds the repo root to ``sys.path``, exposes the declared tool list from
``mcp_tools.get_mcp_tools()``, and forwards every call to
``procurement_core.service.call_tool_text``, wrapping the returned markdown
in a single ``TextContent`` block.

Run directly:            ``python mcp-servers/canadabuys/server.py``
Smoke test:              ``python -m unittest tests.test_canadabuys_mcp_smoke``
Hosted equivalent:       ``server_http.py`` (StreamableHTTP MCP + REST)
"""

import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.service import call_tool_text  # noqa: E402
from mcp_tools import get_mcp_tools  # noqa: E402

server = Server("canadabuys")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available procurement tools."""
    return get_mcp_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle an MCP tool call through the shared procurement core."""
    text = await call_tool_text(name, arguments)
    return [TextContent(type="text", text=text)]


async def main() -> None:
    """Run the stdio MCP server."""
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
