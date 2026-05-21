#!/usr/bin/env python3
"""Hosted MCP and REST/OpenAPI adapter for the shared procurement core."""

import sys
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.service import TOOL_NAMES, call_tool_text, process_bid_room_artifact  # noqa: E402
from mcp_tools import get_mcp_tools  # noqa: E402

mcp_server = Server("canadabuys")
app = FastAPI(
    title="WorkspaceAlberta Procurement API",
    description=(
        "Custom procurement MCP server and REST API for CanadaBuys, "
        "Alberta Purchasing Connection, business-profile matching, daily bid "
        "briefs, and optional Cohere Command A+ analysis."
    ),
    version="0.2.0",
)
sse = SseServerTransport("/messages/")


def serialize_tool(tool: Tool) -> dict[str, Any]:
    """Return a JSON-safe representation of an MCP Tool."""
    if hasattr(tool, "model_dump"):
        return tool.model_dump()
    if hasattr(tool, "dict"):
        return tool.dict()
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.inputSchema,
    }


async def run_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a shared-core tool and return a REST-friendly envelope."""
    if tool_name not in TOOL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    content = await call_tool_text(tool_name, arguments or {})
    return {
        "tool": tool_name,
        "content_type": "text/markdown",
        "content": content,
    }


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available procurement MCP tools."""
    return get_mcp_tools()


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle an MCP tool call through the shared procurement core."""
    text = await call_tool_text(name, arguments)
    return [TextContent(type="text", text=text)]


async def handle_sse(request: Request) -> None:
    """Handle MCP SSE connections."""
    async with sse.connect_sse(
        request.scope,
        request.receive,
        request._send,
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            mcp_server.create_initialization_options(),
        )


async def handle_messages(request: Request) -> None:
    """Handle MCP SSE client messages."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


app.add_route("/sse", handle_sse, methods=["GET"])
app.add_route("/messages/", handle_messages, methods=["POST"])


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    """Report service health without calling upstream procurement sources."""
    return {
        "status": "ok",
        "server": "workspacealberta-procurement",
        "mcp": {"sse": "/sse", "messages": "/messages/"},
        "rest": {"openapi": "/openapi.json", "docs": "/docs"},
        "tools": len(TOOL_NAMES),
    }


@app.get("/tools", tags=["system"])
async def tools() -> dict[str, Any]:
    """List MCP-compatible tools and JSON schemas."""
    return {"tools": [serialize_tool(tool) for tool in get_mcp_tools()]}


@app.post("/tools/{tool_name}", tags=["tools"])
async def generic_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Call any procurement tool by MCP tool name."""
    return await run_tool(tool_name, arguments)


@app.post("/search", tags=["procurement"])
async def search(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Search CanadaBuys and Alberta Purchasing Connection together."""
    return await run_tool("search_opportunities", arguments)


@app.get("/details/{reference}", tags=["procurement"])
async def details(reference: str) -> dict[str, Any]:
    """Get details for a CanadaBuys or Alberta APC opportunity."""
    return await run_tool("get_opportunity_details", {"reference": reference})


@app.post("/deadlines", tags=["procurement"])
async def deadlines(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """List federal and Alberta opportunities closing soon."""
    return await run_tool("list_deadlines", arguments)


@app.post("/matches", tags=["procurement"])
async def matches(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Rank opportunities against the saved business profile."""
    return await run_tool("find_matching_opportunities", arguments)


@app.post("/brief", tags=["procurement"])
async def brief(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Generate the daily bid brief."""
    return await run_tool("daily_bid_brief", arguments)


@app.post("/bid-room/process", tags=["bid-room"])
async def bid_room_process(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Process a bid room in E2B and analyze it with Cohere inside the sandbox."""
    try:
        return process_bid_room_artifact(arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/profile", tags=["profile"])
async def set_profile(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Set the business profile used for opportunity matching."""
    return await run_tool("set_business_profile", arguments)


@app.get("/profile", tags=["profile"])
async def get_profile() -> dict[str, Any]:
    """Return the saved business profile."""
    return await run_tool("get_my_profile", {})


@app.post("/cohere/analyze", tags=["analysis"])
async def cohere_analyze(arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Analyze a CanadaBuys tender with Cohere Command A+ when configured."""
    return await run_tool("analyze_contract_with_cohere", arguments)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
