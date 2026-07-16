#!/usr/bin/env python3
"""Hosted MCP and REST/OpenAPI adapter for the shared procurement core."""

import contextlib
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core.service import TOOL_NAMES, call_tool_text, process_bid_room_artifact  # noqa: E402
from mcp_tools import get_mcp_tools  # noqa: E402

mcp_server = Server("canadabuys")
session_manager: StreamableHTTPSessionManager | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the StreamableHTTP MCP session manager for the app lifetime."""
    global session_manager
    # Built per startup: the SDK allows .run() only once per manager instance.
    # Stateless + JSON: Cloud Run autoscaling routes each request to any
    # instance, so in-memory sessions would intermittently fail with
    # "Missing session ID".
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=True,
        stateless=True,
    )
    async with session_manager.run():
        yield
    session_manager = None


app = FastAPI(
    title="WorkspaceAlberta Procurement API",
    description=(
        "Custom procurement MCP server and REST API for CanadaBuys, "
        "Alberta Purchasing Connection, business-profile matching, daily bid "
        "briefs, and optional Cohere Command A+ analysis."
    ),
    version="0.4.0",
    lifespan=lifespan,
)

# Browser-based MCP clients (web inspectors, playgrounds) need CORS to pass
# preflight; the API is public and read-mostly, so a wildcard is acceptable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id", "mcp-protocol-version"],
)


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


class MCPStreamableHTTPApp:
    """ASGI adapter for the MCP StreamableHTTP session manager."""

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if session_manager is None:
            raise RuntimeError("MCP session manager is not running")
        if scope.get("type") == "http" and scope.get("method") == "GET":
            # The stateless transport has no server-push stream and never
            # answers GET, leaving the connection hanging; fail fast instead.
            response = JSONResponse(
                {"error": "Method Not Allowed. POST JSON-RPC messages to this endpoint."},
                status_code=405,
                headers={"Allow": "POST, DELETE"},
            )
            await response(scope, receive, send)
            return
        if scope.get("type") == "http":
            # The SDK 406s unless the client accepts BOTH application/json and
            # text/event-stream; many simple HTTP clients send only one. The
            # server runs in JSON response mode, so widening Accept is safe.
            headers = [(key, value) for key, value in scope.get("headers", []) if key != b"accept"]
            headers.append((b"accept", b"application/json, text/event-stream"))
            scope = {**scope, "headers": headers}
        await session_manager.handle_request(scope, receive, send)


app.add_route("/mcp", MCPStreamableHTTPApp(), methods=["GET", "POST", "DELETE"])




LANDING_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WorkspaceAlberta Procurement MCP</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 44rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.55; color: #1c1c1c; }}
  code, pre {{ background: #f4f4f4; border-radius: 6px; }}
  code {{ padding: 0.1rem 0.35rem; }}
  pre {{ padding: 1rem; overflow-x: auto; }}
  a {{ color: #0b57d0; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .sub {{ color: #555; margin-top: 0; }}
</style>
</head>
<body>
<h1>WorkspaceAlberta</h1>
<p class="sub">Canadian procurement intelligence over MCP: CanadaBuys + Alberta Purchasing Connection.</p>
<p>This service is live. It searches federal and Alberta public tenders, lists deadlines,
ranks opportunities against your business, and drafts daily bid briefs. No account or API key needed.</p>
<h2>Connect an MCP client</h2>
<p>Add this server to Claude Desktop, Cursor, Cline, VS Code, Zed, or any MCP-capable client:</p>
<pre>{{
  "mcpServers": {{
    "workspaceAlberta": {{
      "type": "http",
      "url": "{mcp_url}"
    }}
  }}
}}</pre>
<h2>Prefer plain REST?</h2>
<p>The same tools are exposed over REST/OpenAPI:
<a href="/docs">interactive docs</a> &middot; <a href="/openapi.json">openapi.json</a> &middot;
<a href="/tools">tool schemas</a> &middot; <a href="/health">health</a></p>
<p>Always open and verify the original tender documents before bidding. This tool triages
and summarizes; it does not replace the source posting.</p>
<p><a href="https://github.com/HarleyCoops/WorkspaceAlberta">Source and documentation on GitHub</a></p>
</body>
</html>
"""


@app.get("/", include_in_schema=False)
async def landing(request: Request) -> HTMLResponse:
    """Human-friendly landing page with MCP connect instructions."""
    base = str(request.base_url).rstrip("/")
    return HTMLResponse(LANDING_PAGE_TEMPLATE.format(mcp_url=f"{base}/mcp"))


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    """Report service health without calling upstream procurement sources."""
    return {
        "status": "ok",
        "server": "workspacealberta-procurement",
        "mcp": {"streamable_http": "/mcp"},
        "rest": {"openapi": "/openapi.json", "docs": "/docs"},
        "tools": len(get_mcp_tools()),
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
