#!/usr/bin/env python3
"""Hosted MCP and REST/OpenAPI adapter for the shared procurement core.

One FastAPI app, two protocols, identical behaviour:

- **MCP over StreamableHTTP** at ``/mcp`` — for MCP-native agents. The
  transport runs stateless with JSON responses (every request is
  self-contained), so Cloud Run autoscaling can route any request to any
  instance without breaking sessions.
- **REST/OpenAPI** — for everything that can't speak MCP. ``/tools`` lists
  the same tool schemas the MCP side declares; ``POST /tools/{tool_name}``
  calls any tool generically; and named convenience routes (``/search``,
  ``/details/{reference}``, ``/deadlines``, ``/matches``, ``/brief``,
  ``/bid-room/process``, ``/profile``, ``/cohere/analyze``) map one-to-one
  onto the highest-value tools. Interactive docs at ``/docs``, schema at
  ``/openapi.json``, liveness at ``/health`` (no upstream calls).

Agent-discovery documents are served under ``/.well-known`` (A2A agent card,
RFC 9728 protected-resource metadata, RFC 8414 auth-server metadata, and an
``mcp.json`` mirroring the registry entry) because registries and scanners
crawl those paths as soon as the endpoint is listed.

Both paths dispatch into ``procurement_core.service.call_tool_text``, so a
REST caller and an MCP agent always get byte-identical markdown for the same
tool and arguments. The bid-room route is the one exception: it returns the
full JSON artifact envelope from ``process_bid_room_artifact`` (sandbox id,
artifact, rendered markdown) and maps payload errors to 400 and missing
runtime dependencies (E2B/Cohere keys) to 503.

Deploy: ``uvicorn server_http:app`` (see Dockerfile, Procfile, railway.json
in this directory). Local run: ``python server_http.py`` serves on :8000.
"""

import asyncio
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

from procurement_core import storage  # noqa: E402
from procurement_core.auth import (  # noqa: E402
    GateError,
    PRO_TOOLS,
    check_tool_access,
    extract_bearer_key,
    gate_enabled,
    validate_key,
)
from procurement_core.billing import WebhookError, process_webhook_event  # noqa: E402
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
# preflight; the API is public, so a wildcard is acceptable. Authorization
# headers still apply per request for Pro tools.
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


async def run_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    authorization: str | None = None,
) -> dict[str, Any]:
    """Run a shared-core tool and return a REST-friendly envelope.

    Pro tools (see ``auth.PRO_TOOLS``) require a valid subscriber Bearer key
    when the gate is enabled; the subscriber's key hash becomes the tenant
    context so profile/watchlist reads hit their own row.
    """
    if tool_name not in TOOL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    try:
        # Key validation hits Supabase/Stripe with blocking urlopen on cache
        # misses; keep it off the event loop.
        record = await asyncio.to_thread(check_tool_access, tool_name, authorization)
    except GateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    token = storage.set_tenant(record["key_hash"]) if record else None
    try:
        content = await call_tool_text(tool_name, arguments or {})
    finally:
        if token is not None:
            storage.reset_tenant(token)
    return {
        "tool": tool_name,
        "content_type": "text/markdown",
        "content": content,
    }


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available procurement MCP tools."""
    return get_mcp_tools()


def _mcp_authorization_header() -> str | None:
    """Read the Authorization header from the current MCP request context."""
    try:
        ctx = mcp_server.request_context
    except LookupError:
        return None
    request = getattr(ctx, "request", None)
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    return headers.get("authorization")


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle an MCP tool call through the shared procurement core.

    Applies the same Pro-tool gate as REST: the Bearer key is read from the
    StreamableHTTP request headers via the MCP request context. Gate
    failures return a readable message (MCP has no HTTP status per tool
    call) telling the caller how to subscribe or configure their key.
    """
    try:
        record = await asyncio.to_thread(check_tool_access, name, _mcp_authorization_header())
    except GateError as exc:
        return [
            TextContent(
                type="text",
                text=(
                    f"# WorkspaceAlberta Pro required\n\n{exc}\n\n"
                    "Add your key to the MCP server config as an "
                    '`Authorization: Bearer wa_live_...` header, or subscribe at '
                    "https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a ($85 CAD/month)."
                ),
            )
        ]

    token = storage.set_tenant(record["key_hash"]) if record else None
    try:
        text = await call_tool_text(name, arguments)
    finally:
        if token is not None:
            storage.reset_tenant(token)
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
<p>This service is live. Search federal and Alberta public tenders, list deadlines,
rank opportunities against your business, and get daily bid briefs — free, no key needed.
Pro tools (bid-room processing, Cohere tender analysis, watchlists) use a subscriber key.</p>
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
<p>Pro subscribers add their key as an <code>Authorization: Bearer wa_live_...</code> header
in the same config block, and can check it at <a href="/me">/me</a>.</p>
<h2>Prefer plain REST?</h2>
<p>The same tools are exposed over REST/OpenAPI:
<a href="/docs">interactive docs</a> &middot; <a href="/openapi.json">openapi.json</a> &middot;
<a href="/tools">tool schemas</a> &middot; <a href="/health">health</a></p>
<p>Agent registries: <a href="/.well-known/agent.json">agent card (A2A)</a> &middot;
<a href="/.well-known/mcp.json">mcp.json</a> &middot;
<a href="/.well-known/oauth-protected-resource">protected-resource metadata</a></p>
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
        "tools": len(TOOL_NAMES),
        "gate": {
            "enabled": gate_enabled(),
            "pro_tools": sorted(PRO_TOOLS),
        },
    }


@app.get("/me", tags=["system"])
async def me(request: Request) -> dict[str, Any]:
    """Validate the caller's Bearer key and report subscription status."""
    key = extract_bearer_key(request.headers.get("authorization"))
    if not key:
        raise HTTPException(status_code=401, detail="Send your key as `Authorization: Bearer wa_live_...`.")
    try:
        record = await asyncio.to_thread(validate_key, key)
    except GateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {
        "status": record.get("status"),
        "plan": record.get("plan"),
        "email": record.get("email", ""),
        "pro_tools": sorted(PRO_TOOLS),
    }


# ---------------------------------------------------------------------------
# Agent-discovery documents.
#
# Agent registries and security scanners crawl these well-known paths within
# hours of an MCP registry publish (observed in production access logs). All
# are derived from request.base_url so they stay correct on any host.
# ---------------------------------------------------------------------------

STRIPE_SUBSCRIBE_URL = "https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a"
REPO_URL = "https://github.com/HarleyCoops/WorkspaceAlberta"


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _agent_card(base: str) -> dict[str, Any]:
    """Build an A2A agent card from the live tool list.

    Skills mirror the MCP tools exactly, so the card can never drift from
    what the server actually exposes. Pro tools are tagged, not hidden —
    anonymous callers can still use every free tool.
    """
    skills = []
    for tool in get_mcp_tools():
        tags = ["procurement", "canada"]
        if "alberta" in tool.name:
            tags.append("alberta")
        if tool.name in PRO_TOOLS:
            tags.append("pro")
        description = (tool.description or "").strip().splitlines()[0] if tool.description else ""
        skills.append(
            {
                "id": tool.name,
                "name": tool.name.replace("_", " ").title(),
                "description": description[:300],
                "tags": tags,
            }
        )
    return {
        "name": "WorkspaceAlberta Procurement",
        "description": (
            "Canadian procurement intelligence over MCP: search CanadaBuys and "
            "Alberta Purchasing Connection tenders, list closing deadlines, rank "
            "opportunities against a business profile, and generate daily bid briefs."
        ),
        "url": f"{base}/mcp",
        "provider": {"organization": "Warre and Vavasour", "url": "https://warreandvavasour.com"},
        "version": app.version,
        "documentationUrl": REPO_URL,
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        # Legacy A2A drafts read `authentication`; current drafts read
        # `securitySchemes`/`security`. Serve both so any crawler version
        # understands the Pro-tool gate.
        "authentication": {
            "schemes": ["Bearer"],
            "credentials": (
                "Pro tools require a subscriber key sent as "
                "`Authorization: Bearer wa_live_...`. Search, deadline, and "
                "brief tools are free without a key."
            ),
        },
        "securitySchemes": {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "Subscriber key (wa_live_...) for Pro tools.",
            }
        },
        "security": [{"bearer": []}],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["text/markdown"],
        "skills": skills,
    }


@app.get("/.well-known/agent.json", include_in_schema=False)
@app.get("/.well-known/agent-card.json", include_in_schema=False)
@app.get("/agents/.well-known/agent-card.json", include_in_schema=False)
@app.get("/mcp/.well-known/agent-card.json", include_in_schema=False)
async def agent_card(request: Request) -> JSONResponse:
    """A2A agent card at every location crawlers have asked for."""
    return JSONResponse(_agent_card(_base_url(request)))


@app.get("/agent/authenticatedExtendedCard", include_in_schema=False)
async def authenticated_extended_card(request: Request) -> JSONResponse:
    """A2A extended card: 401 without a key, subscriber view with one."""
    key = extract_bearer_key(request.headers.get("authorization"))
    if not key:
        return JSONResponse(
            {"error": "Send `Authorization: Bearer wa_live_...` for the extended card."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        validate_key(key)
    except GateError as exc:
        return JSONResponse(
            {"error": str(exc)},
            status_code=exc.status_code,
            headers={"WWW-Authenticate": "Bearer"},
        )
    card = _agent_card(_base_url(request))
    card["authenticated"] = True
    card["proTools"] = sorted(PRO_TOOLS)
    return JSONResponse(card)


@app.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def oauth_protected_resource(request: Request) -> JSONResponse:
    """RFC 9728 protected-resource metadata for the MCP endpoint."""
    base = _base_url(request)
    return JSONResponse(
        {
            "resource": f"{base}/mcp",
            "authorization_servers": [base],
            "bearer_methods_supported": ["header"],
            "resource_documentation": REPO_URL,
        }
    )


@app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_authorization_server(request: Request) -> JSONResponse:
    """RFC 8414 metadata.

    This server is not a real OAuth authorization server: subscriber keys are
    issued through Stripe checkout and validated per request, so the grant
    and response type lists are honestly empty. Extra members are permitted
    by RFC 8414; ``subscription_key_registration`` tells crawlers where a
    human actually gets a key.
    """
    base = _base_url(request)
    return JSONResponse(
        {
            "issuer": base,
            "grant_types_supported": [],
            "response_types_supported": [],
            "token_endpoint_auth_methods_supported": [],
            "service_documentation": REPO_URL,
            "op_policy_uri": f"{base}/",
            "subscription_key_registration": STRIPE_SUBSCRIBE_URL,
        }
    )


@app.get("/.well-known/mcp.json", include_in_schema=False)
async def mcp_well_known(request: Request) -> JSONResponse:
    """MCP server-discovery document mirroring the registry server.json.

    Values duplicate the repo-root server.json on purpose: the Docker image
    only ships procurement_core and mcp-servers/canadabuys, so the registry
    file is not readable at runtime. Keep both in sync when bumping.
    """
    base = _base_url(request)
    return JSONResponse(
        {
            "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
            "name": "io.github.HarleyCoops/workspace-alberta",
            "description": (
                "Canadian procurement intelligence: CanadaBuys and Alberta "
                "tenders, ranked for your shop."
            ),
            "version": app.version,
            "repository": {"url": REPO_URL, "source": "github"},
            "remotes": [{"type": "streamable-http", "url": f"{base}/mcp"}],
        }
    )


@app.post("/stripe/webhook", tags=["billing"])
async def stripe_webhook(request: Request) -> JSONResponse:
    """Stripe webhook: provisions subscribers and revokes cancelled ones.

    Verifies the ``Stripe-Signature`` header against
    ``STRIPE_WEBHOOK_SECRET`` before touching anything. Handles
    ``checkout.session.completed`` (issue key, upsert Supabase row, mirror
    key into Stripe customer metadata) and ``customer.subscription.deleted``
    (revoke). All other events are acknowledged and ignored.
    """
    payload = await request.body()
    try:
        # Provisioning does several blocking Supabase/Stripe round-trips.
        result = await asyncio.to_thread(
            process_webhook_event, payload, request.headers.get("stripe-signature")
        )
    except WebhookError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return JSONResponse(result)


@app.get("/tools", tags=["system"])
async def tools() -> dict[str, Any]:
    """List MCP-compatible tools and JSON schemas."""
    return {"tools": [serialize_tool(tool) for tool in get_mcp_tools()]}


def _auth(request: Request) -> str | None:
    return request.headers.get("authorization")


@app.post("/tools/{tool_name}", tags=["tools"])
async def generic_tool(
    tool_name: str,
    request: Request,
    arguments: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    """Call any procurement tool by MCP tool name."""
    return await run_tool(tool_name, arguments, _auth(request))


@app.post("/search", tags=["procurement"])
async def search(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Search CanadaBuys and Alberta Purchasing Connection together."""
    return await run_tool("search_opportunities", arguments, _auth(request))


@app.get("/details/{reference}", tags=["procurement"])
async def details(reference: str, request: Request) -> dict[str, Any]:
    """Get details for a CanadaBuys or Alberta APC opportunity."""
    return await run_tool("get_opportunity_details", {"reference": reference}, _auth(request))


@app.post("/deadlines", tags=["procurement"])
async def deadlines(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """List federal and Alberta opportunities closing soon."""
    return await run_tool("list_deadlines", arguments, _auth(request))


@app.post("/matches", tags=["procurement"])
async def matches(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Rank opportunities against the saved business profile."""
    return await run_tool("find_matching_opportunities", arguments, _auth(request))


@app.post("/brief", tags=["procurement"])
async def brief(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Generate the daily bid brief."""
    return await run_tool("daily_bid_brief", arguments, _auth(request))


@app.post("/bid-room/process", tags=["bid-room"])
async def bid_room_process(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Process a bid room in E2B and analyze it with Cohere inside the sandbox.

    Pro-gated: requires a valid subscriber Bearer key when the gate is on.
    """
    try:
        record = await asyncio.to_thread(check_tool_access, "process_bid_room", _auth(request))
    except GateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    token = storage.set_tenant(record["key_hash"]) if record else None
    try:
        # E2B sandbox processing blocks for minutes; keep it off the event loop.
        return await asyncio.to_thread(process_bid_room_artifact, arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if token is not None:
            storage.reset_tenant(token)


@app.post("/profile", tags=["profile"])
async def set_profile(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Set the business profile used for opportunity matching."""
    return await run_tool("set_business_profile", arguments, _auth(request))


@app.get("/profile", tags=["profile"])
async def get_profile(request: Request) -> dict[str, Any]:
    """Return the saved business profile."""
    return await run_tool("get_my_profile", {}, _auth(request))


@app.post("/cohere/analyze", tags=["analysis"])
async def cohere_analyze(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Analyze a CanadaBuys tender with Cohere Command A+ when configured."""
    return await run_tool("analyze_contract_with_cohere", arguments, _auth(request))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
