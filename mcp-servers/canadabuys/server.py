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

from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.service import call_tool_text_and_structured  # noqa: E402
from mcp_tools import get_mcp_tools  # noqa: E402

async def handle_list_tools(ctx: ServerRequestContext, params) -> ListToolsResult:
    """List available procurement tools."""
    return ListToolsResult(tools=get_mcp_tools())


async def handle_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    """Handle an MCP tool call through the shared procurement core."""
    text, structured = await call_tool_text_and_structured(params.name, params.arguments or {})
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=structured,
        is_error=False,
    )


server = Server("canadabuys", on_list_tools=handle_list_tools, on_call_tool=handle_call_tool)


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
