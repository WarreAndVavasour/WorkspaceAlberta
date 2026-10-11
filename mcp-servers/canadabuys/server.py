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
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.service import call_tool_text_and_structured, mcp_text_blocks  # noqa: E402
from mcp_tools import get_mcp_tools  # noqa: E402
from procurement_core.agent_contract import SERVER_INSTRUCTIONS  # noqa: E402


# Stdio-only tools. They read this machine's filesystem, so they are never
# added to ``get_mcp_tools()`` (shared with the hosted HTTP server).
LOCAL_BID_ROOM_TOOL = Tool(
    name="process_local_bid_room",
    title="Process downloaded APC documents",
    description=(
        "Review APC tender documents already downloaded to this machine by the APC connector "
        "(saved under WA_APC_HOME/opportunities/<reference>/). Re-verifies each file's SHA-256 "
        "against the download receipt, uploads verified files to a fresh E2B sandbox, and runs "
        "the same extraction, coverage checks and Cohere Command A+ review as process_bid_room. "
        "Sends the documents to E2B and their contents to Cohere; confirm the posting's terms "
        "allow that. Never signs in to APC or downloads anything. An incomplete download or "
        "partial coverage is not a complete RFP review."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "reference": {"type": "string", "description": "APC reference, e.g. AB-2026-06523"},
            "business_context": {
                "type": "string",
                "description": "Optional company capabilities or bid context. If omitted, the saved business profile is used.",
            },
            "max_attachments": {
                "type": "integer", "default": 5, "minimum": 0, "maximum": 5,
                "description": "Maximum downloaded files to process (default 5, max 5).",
            },
        },
        "required": ["reference"],
        "additionalProperties": False,
    },
)
LOCAL_TOOLS = [LOCAL_BID_ROOM_TOOL]
LOCAL_BID_ROOM_CALL_SECONDS = 150


async def handle_list_tools(ctx: ServerRequestContext, params) -> ListToolsResult:
    """List available procurement tools plus local-only tools."""
    return ListToolsResult(tools=[*get_mcp_tools(), *LOCAL_TOOLS])


async def call_local_bid_room(arguments: dict) -> CallToolResult:
    import asyncio
    from procurement_core.local_bid_room import LocalBidRoomError, process_local_bid_room_artifact
    from procurement_core.e2b_bid_room import BidRoomTimeout

    try:
        envelope = await asyncio.wait_for(
            asyncio.to_thread(process_local_bid_room_artifact, dict(arguments)),
            timeout=LOCAL_BID_ROOM_CALL_SECONDS,
        )
    except (LocalBidRoomError, BidRoomTimeout, RuntimeError, TimeoutError) as exc:
        message = str(exc) or "The local bid room timed out. Retry with fewer attachments."
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {message}")], is_error=True)
    structured = {key: value for key, value in envelope.items() if key != "markdown"}
    return CallToolResult(
        content=[TextContent(type="text", text=envelope["markdown"])],
        structured_content=structured,
        is_error=False,
    )


async def handle_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    """Handle an MCP tool call through the shared procurement core."""
    if params.name == LOCAL_BID_ROOM_TOOL.name:
        return await call_local_bid_room(params.arguments or {})
    text, structured = await call_tool_text_and_structured(params.name, params.arguments or {})
    return CallToolResult(
        content=[TextContent(type="text", text=block) for block in mcp_text_blocks(params.name, text, structured)],
        structured_content=structured,
        is_error=text.startswith("Error:"),
    )


server = Server(
    "canadabuys",
    instructions=SERVER_INSTRUCTIONS,
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)


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
