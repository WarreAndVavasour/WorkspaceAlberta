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
  ``/bid-room/process``, ``/bid-room/classify``, ``/profile``,
  ``/cohere/analyze``) map one-to-one
  onto the highest-value tools. Interactive docs at ``/docs``, schema at
  ``/openapi.json``, liveness at ``/health`` (no upstream calls).

Agent-discovery documents are served under ``/.well-known`` (A2A agent card,
RFC 9728 protected-resource metadata, RFC 8414 authorization-server metadata,
and an ``mcp.json`` mirroring the registry entry). The hosted app is also its
own OAuth 2.1 authorization server (PKCE, DCR, CIMD) so Claude can sign a
user in; see ``docs/oauth.md``.

Both paths dispatch into ``procurement_core.service.call_tool_text``, so a
REST caller and an MCP agent always get byte-identical markdown for the same
tool and arguments. The bid-room routes are the exception: they return the
full JSON artifact envelope from ``process_bid_room_artifact`` (sandbox id,
artifact, rendered markdown) or ``classify_tender_artifact`` (artifact,
rendered markdown) and map payload errors to 400 and missing runtime
dependencies (E2B/Cohere/TypeSafe keys) to 503. Over MCP, ``classify_tender``
also returns its structured content as a second, JSON text block
(``mcp_text_blocks``).

Deploy: ``uvicorn server_http:app`` (see Dockerfile, Procfile, railway.json
in this directory). Local run: ``python server_http.py`` serves on :8000.
"""

import asyncio
import contextlib
import json
import sys
import time
from datetime import datetime, timezone
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from mcp.server import Server, ServerRequestContext
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool
from mcp_types import CLIENT_INFO_META_KEY

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from procurement_core import identity, oauth, storage, telemetry, usage  # noqa: E402
from procurement_core import http_hardening  # noqa: E402
from procurement_core.auth import (  # noqa: E402
    GateError,
    PRO_TOOLS,
    PROTECTED_TOOLS,
    SIGN_IN_TOOLS,
    extract_bearer_key,
    gate_enabled,
    validate_key,
)
from procurement_core.billing import WebhookError, process_webhook_event  # noqa: E402
from procurement_core.identity import check_tool_access, tenant_id_for  # noqa: E402
from procurement_core.oauth_http import register_oauth_routes  # noqa: E402
from procurement_core.bid_room_upload_http import register_bid_room_upload_routes  # noqa: E402
from procurement_core.public_pages import register_public_pages  # noqa: E402
from procurement_core import web_pages  # noqa: E402
from procurement_core.service import (  # noqa: E402
    TOOL_NAMES,
    ClassifierNotConfigured,
    call_tool_text,
    call_tool_text_and_structured,
    mcp_text_blocks,
    classify_tender_artifact_bounded,
    process_bid_room_artifact_bounded,
)
from mcp_tools import get_mcp_tools  # noqa: E402
from procurement_core.agent_contract import SERVER_INSTRUCTIONS, workflow_contract  # noqa: E402

def _mcp_authorization_header(ctx: ServerRequestContext) -> str | None:
    """Read the Authorization header from the current MCP request context."""
    request = getattr(ctx, "request", None)
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    return headers.get("authorization")


def _mcp_caller(ctx: ServerRequestContext) -> dict[str, Any]:
    """Telemetry caller context for the current MCP request."""
    request = getattr(ctx, "request", None)
    headers = getattr(request, "headers", None) or {}
    client = getattr(request, "client", None)
    meta = getattr(ctx, "meta", None)
    client_info = meta.get(CLIENT_INFO_META_KEY) if isinstance(meta, dict) else None
    return telemetry.caller_context(
        headers,
        transport="mcp",
        peer=getattr(client, "host", None),
        client_info=client_info if isinstance(client_info, dict) else None,
        protocol_version=getattr(ctx, "protocol_version", None) if client_info else None,
    )


def _rest_caller(request: Request, transport: str = "rest") -> dict[str, Any]:
    """Telemetry caller context for a REST call (or ``transport="web"`` for a page)."""
    return telemetry.caller_context(
        request.headers,
        transport=transport,
        peer=request.client.host if request.client else None,
    )


async def handle_list_tools(ctx: ServerRequestContext, params) -> ListToolsResult:
    """List available procurement MCP tools."""
    from procurement_core.openai_support import OpenAIListToolsResult
    return OpenAIListToolsResult(tools=get_mcp_tools())


async def handle_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    """Handle an MCP tool call through the shared procurement core.

    Applies the same Pro-tool gate as REST: the Bearer key is read from the
    StreamableHTTP request headers via the MCP request context. Gate
    The HTTP gate challenges missing/invalid identities before dispatch.
    Denials that reach the handler (such as an inactive subscription) are
    tool errors, so clients can distinguish them from successful results.
    """
    name = params.name
    arguments = params.arguments or {}
    caller = _mcp_caller(ctx)
    try:
        record = await asyncio.to_thread(check_tool_access, name, _mcp_authorization_header(ctx))
    except GateError as exc:
        telemetry.capture_gate_denied(name, "mcp", exc.status_code, caller=caller)
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"# workspaceAlberta access required\n\n{exc}\n\n"
                        "Sign in when your client prompts. Saved profiles are free; "
                        "only Pro tools require a separate subscription."
                    ),
                )
            ],
            is_error=True,
            _meta={"mcp/www_authenticate": [oauth.www_authenticate_challenge()]}
            if exc.status_code == 401 else None,
        )

    token = storage.set_tenant(tenant_id_for(record)) if record else None
    started = time.monotonic()
    try:
        with usage.metering() as meter:
            text, structured = await call_tool_text_and_structured(name, arguments)
    finally:
        if token is not None:
            storage.reset_tenant(token)
    telemetry.capture_tool_call(
        name, "mcp", record, arguments, text, int((time.monotonic() - started) * 1000),
        upstream=meter.log_fields(), caller=caller,
    )
    return CallToolResult(
        content=[TextContent(type="text", text=block) for block in mcp_text_blocks(name, text, structured)],
        structured_content=structured,
        is_error=text.startswith("Error:"),
    )


mcp_server = Server(
    "canadabuys",
    version="1.3.0",
    instructions=SERVER_INSTRUCTIONS,
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)
from procurement_core.openai_wire import preserve_auth_metadata
mcp_server.middleware.append(preserve_auth_metadata)
session_manager: StreamableHTTPSessionManager | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the StreamableHTTP MCP session manager for the app lifetime."""
    global session_manager
    oauth.validate_hosted_configuration()
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
        "workspaceAlberta procurement API for every CanadaBuys and Alberta "
        "Purchasing Connection notice, matched to any business, with Buy "
        "Canadian signals, daily bid briefs, and a read-only industrial "
        "support catalog."
    ),
    version="1.3.0",
    lifespan=lifespan,
    # Swagger lists tags in this order: what a first-time visitor wants first.
    openapi_tags=[
        {"name": "procurement", "description": "Search tenders, details, deadlines, matches and briefs. Free."},
        {"name": "profile", "description": "Save or read your business profile (free sign-in)."},
        {"name": "bid-room", "description": "Pro: tender document review."},
        {"name": "analysis", "description": "Pro: Cohere tender analysis."},
        {"name": "tools", "description": "Call any tool by its MCP name."},
        {"name": "system", "description": "Health, tool list and token status."},
    ],
)

# Browser-based MCP clients (web inspectors, playgrounds) need CORS to pass
# preflight; the API is public, so a wildcard is acceptable. Authorization
# headers still apply per request for Pro tools.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id", "mcp-protocol-version", "WWW-Authenticate"],
)
register_oauth_routes(app)
register_bid_room_upload_routes(app)
register_public_pages(app)
# Added last, so it is the outermost layer: it sees every response, and keeps
# any header a route (such as the OAuth sign-in pages) already set.
app.add_middleware(http_hardening.SecurityHeadersMiddleware)


def serialize_tool(tool: Tool) -> dict[str, Any]:
    """Return a JSON-safe representation of an MCP Tool with wire-case keys."""
    return tool.model_dump(by_alias=True, exclude_none=True)


MAX_REST_STRING = 2000


def _tool_schema(tool_name: str) -> dict[str, Any]:
    for tool in get_mcp_tools():
        if tool.name == tool_name:
            return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}
    return {}


_JSON_TYPES = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_rest_arguments(tool_name: str, arguments: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Check REST arguments against the tool's input schema.

    REST callers (people in /docs, scripts) get a 422 that names the bad field
    instead of a silently ignored field or an internal error string. The MCP
    path is unchanged.
    """
    if arguments is None:
        return []
    if not isinstance(arguments, dict):
        return [{"loc": ["body"], "msg": "The request body must be a JSON object."}]
    schema = _tool_schema(tool_name)
    properties: dict[str, Any] = schema.get("properties") or {}
    errors: list[dict[str, Any]] = []
    for key, value in arguments.items():
        spec = properties.get(key)
        if spec is None:
            if isinstance(schema.get("additionalProperties"), dict):
                continue  # schema explicitly allows typed extra fields
            if properties:
                errors.append({
                    "loc": ["body", key],
                    "msg": f"Unknown field '{key}'. Valid fields: {', '.join(sorted(properties))}.",
                })
            continue
        expected = spec.get("type")
        allowed = _JSON_TYPES.get(expected) if isinstance(expected, str) else None
        if value is None:
            continue
        if allowed and (not isinstance(value, allowed) or (expected in {"integer", "number"} and isinstance(value, bool))):
            errors.append({"loc": ["body", key], "msg": f"'{key}' must be {'an' if expected[0] in 'aeiou' else 'a'} {expected}."})
            continue
        if isinstance(value, str) and len(value) > MAX_REST_STRING:
            errors.append({"loc": ["body", key], "msg": f"'{key}' is too long (max {MAX_REST_STRING} characters)."})
        if expected == "integer" and key in {"limit", "days"} and value < 1:
            errors.append({"loc": ["body", key], "msg": f"'{key}' must be 1 or more."})
        if spec.get("enum") and value not in spec["enum"]:
            errors.append({"loc": ["body", key], "msg": f"'{key}' must be one of: {', '.join(map(str, spec['enum']))}."})
    if "source" in properties and isinstance(arguments.get("source"), str):
        if arguments["source"].strip().lower() not in {"", "all", "both", "federal", "canadabuys", "canada", "national", "alberta", "apc"}:
            errors.append({"loc": ["body", "source"], "msg": "'source' must be all, federal or alberta."})
    return errors


async def run_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    authorization: str | None = None,
    caller: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a shared-core tool and return a REST-friendly envelope.

    Pro tools (see ``auth.PRO_TOOLS``) require a valid subscriber Bearer key
    when the gate is enabled; the subscriber's key hash becomes the tenant
    context so profile/watchlist reads hit their own row.
    """
    if tool_name not in TOOL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
    errors = validate_rest_arguments(tool_name, arguments)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    try:
        # Key validation hits Supabase/Stripe with blocking urlopen on cache
        # misses; keep it off the event loop.
        record = await asyncio.to_thread(check_tool_access, tool_name, authorization)
    except GateError as exc:
        telemetry.capture_gate_denied(tool_name, "rest", exc.status_code, caller=caller)
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = oauth.www_authenticate_challenge()
        raise HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers) from exc

    token = storage.set_tenant(tenant_id_for(record)) if record else None
    started = time.monotonic()
    try:
        with usage.metering() as meter:
            content = await call_tool_text(tool_name, arguments or {})
    finally:
        if token is not None:
            storage.reset_tenant(token)
    telemetry.capture_tool_call(
        tool_name, "rest", record, arguments, content, int((time.monotonic() - started) * 1000),
        upstream=meter.log_fields(), caller=caller,
    )
    return {
        "tool": tool_name,
        "content_type": "text/markdown",
        "content": content,
    }


async def _read_http_body(receive: Any, limit: int | None = None) -> bytes:
    """Read the whole request body; raise ``BodyTooLarge`` past ``limit`` bytes."""
    chunks: list[bytes] = []
    size = 0
    more = True
    while more:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b""
        if message["type"] == "http.request":
            chunk = message.get("body") or b""
            size += len(chunk)
            if limit is not None and size > limit:
                raise http_hardening.BodyTooLarge(size)
            chunks.append(chunk)
            more = bool(message.get("more_body"))
        else:
            more = False
    return b"".join(chunks)


def _replay_receive(body: bytes):
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _header_value(scope: dict[str, Any], name: str) -> str | None:
    target = name.lower().encode("ascii")
    for key, value in scope.get("headers") or []:
        if key == target:
            return value.decode("latin-1")
    return None


def _with_session_id(send: Any, payload: Any, scope: dict[str, Any]) -> Any:
    """Answer ``initialize`` with an ``Mcp-Session-Id`` that records ``clientInfo``.

    The transport is stateless, so the id is the session record itself
    (:func:`telemetry.mint_session_id`); clients echo it on every later
    request and telemetry reads the client name back from it. A client that
    already holds one keeps it.
    """
    if not isinstance(payload, dict) or payload.get("method") != "initialize":
        return send
    if _header_value(scope, "mcp-session-id"):
        return send
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    client_info = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else {}
    session_id = telemetry.mint_session_id(
        client_info.get("name"), client_info.get("version"), params.get("protocolVersion")
    )

    async def send_with_session(message: dict[str, Any]) -> None:
        if message.get("type") == "http.response.start" and message.get("status") == 200:
            headers = [(k, v) for k, v in message.get("headers") or [] if k.lower() != b"mcp-session-id"]
            headers.append((b"mcp-session-id", session_id.encode("ascii")))
            message = {**message, "headers": headers}
        await send(message)

    return send_with_session


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
        body = b""
        if scope.get("type") == "http":
            limit = http_hardening.body_limit_bytes()
            declared = _header_value(scope, "content-length") or ""
            try:
                if declared.isdigit() and int(declared) > limit:
                    raise http_hardening.BodyTooLarge(int(declared))
                body = await _read_http_body(receive, limit)
            except http_hardening.BodyTooLarge:
                http_hardening.security_event("mcp_body_too_large", limit=limit)
                response = JSONResponse(
                    {"error": "request_too_large", "error_description": f"MCP request bodies are limited to {limit} bytes."},
                    status_code=413,
                )
                await response(scope, _replay_receive(b""), send)
                return
            try:
                payload = json.loads(body) if body else None
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = None
            send = _with_session_id(send, payload, scope)
            # Partial auth: all protected tools must 401 at the
            # HTTP layer *before* the SDK wraps the refusal in a 200 tool
            # result. initialize, tools/list, and free tools stay open.
            if (gate_enabled() or storage.is_hosted()) and body:
                if payload is not None and oauth.mcp_calls_pro_tool(payload, PROTECTED_TOOLS):
                    authorization = _header_value(scope, "authorization")
                    if not await asyncio.to_thread(identity.has_presentable_identity, authorization):
                        response = JSONResponse(
                            {
                                "error": "invalid_token",
                                "error_description": "Authentication required for this tool",
                            },
                            status_code=401,
                            headers={"WWW-Authenticate": oauth.www_authenticate_challenge()},
                        )
                        await response(scope, _replay_receive(b""), send)
                        return
            # The SDK 406s unless the client accepts BOTH application/json and
            # text/event-stream; many simple HTTP clients send only one. The
            # server runs in JSON response mode, so widening Accept is safe.
            headers = [(key, value) for key, value in scope.get("headers", []) if key != b"accept"]
            headers.append((b"accept", b"application/json, text/event-stream"))
            scope = {**scope, "headers": headers}
            receive = _replay_receive(body)
        await session_manager.handle_request(scope, receive, send)


app.add_route("/mcp", MCPStreamableHTTPApp(), methods=["GET", "POST", "DELETE"])


@app.get("/", include_in_schema=False)
async def landing(request: Request) -> HTMLResponse:
    """Human-friendly landing page with MCP connect instructions.

    Browsers count as ``landing_page_viewed``; MCP clients, crawlers and
    scripts probing the root count as ``endpoint_root_hit``.
    """
    caller = _rest_caller(request, "web")
    is_browser = caller["ua_family"] == "browser"
    telemetry.capture(
        "landing_page_viewed" if is_browser else "endpoint_root_hit",
        caller=caller,
        properties={"source": "direct", "is_browser": is_browser},
    )
    return HTMLResponse(web_pages.landing_page(_public_mcp_url(request)))


def _public_mcp_url(request: Request) -> str:
    """The one connection URL shown to people.

    Always the public origin (custom domain, or ``WA_PUBLIC_MCP_URL``) —
    never the Cloud Run host the proxy forwards to — so every page shows the
    same address and the OAuth resource check matches what clients paste.
    """
    return oauth.public_mcp_resource()


@app.get("/pricing", include_in_schema=False)
async def pricing_page(request: Request) -> HTMLResponse:
    telemetry.capture("pricing_page_viewed", caller=_rest_caller(request, "web"), properties={"source": "direct"})
    return HTMLResponse(web_pages.pricing_page())


@app.api_route("/terms", methods=["GET", "HEAD"], include_in_schema=False)
async def terms_page() -> RedirectResponse:
    return RedirectResponse("/pricing#terms", status_code=302)


@app.get("/developers", include_in_schema=False)
async def developers_page(request: Request) -> HTMLResponse:
    return HTMLResponse(web_pages.developers_page(_public_mcp_url(request)))


@app.get("/try", include_in_schema=False)
async def try_page() -> HTMLResponse:
    return HTMLResponse(web_pages.try_page())


@app.post("/try/search", include_in_schema=False)
async def try_search(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> JSONResponse:
    """Browser search for the /try page: structured records, plain-language errors."""
    args = arguments if isinstance(arguments, dict) else {}
    keywords = args.get("keywords")
    if not isinstance(keywords, str) or not keywords.strip():
        return JSONResponse({"message": "Type a word to search for, for example: concrete."}, status_code=422)
    if len(keywords) > 200:
        return JSONResponse({"message": "Please use 200 characters or fewer."}, status_code=422)
    source = args.get("source") if args.get("source") in {"all", "federal", "alberta"} else "all"
    started = time.monotonic()
    try:
        _, structured = await call_tool_text_and_structured(
            "search_opportunities", {"keywords": keywords.strip(), "source": source, "limit": 20}
        )
    except Exception:  # noqa: BLE001 - never show internals to a browser visitor
        structured = None
    telemetry.capture(
        "try_search", caller=_rest_caller(request, "web"),
        properties={"source": source, "ms": int((time.monotonic() - started) * 1000)},
    )
    if not structured:
        return JSONResponse({"message": "Search did not work just now. Please try again in a minute."}, status_code=502)
    now = datetime.now(timezone.utc)

    def _still_open(record: dict[str, Any]) -> bool:
        closes_at = record.get("closes_at")
        if not closes_at:
            return True
        try:
            return datetime.fromisoformat(closes_at) >= now
        except ValueError:
            return True

    records = [r for r in structured.get("opportunities") or [] if _still_open(r)]
    sources = sorted({r.get("source") for r in records if r.get("source")})
    summary = (f"{len(records)} open tender{'s' if len(records) != 1 else ''} for “{keywords.strip()}” "
               f"from {' and '.join(sources) or 'the sources'}.")
    return JSONResponse({
        "summary": summary,
        "opportunities": records,
        "warnings": [w for w in structured.get("warnings") or [] if not any(t in w.lower() for t in ("fallback", "cache", "planner"))][:3],
    })


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


def _wants_html(request: Request) -> bool:
    """True for a person's browser navigating to a page (not fetch/API/MCP calls)."""
    accept = request.headers.get("accept", "")
    return request.method == "GET" and "text/html" in accept


@app.get("/me", tags=["system"], response_model=None)
async def me(request: Request) -> dict[str, Any] | HTMLResponse:
    """Validate the caller's OAuth token or legacy key and report status."""
    if not extract_bearer_key(request.headers.get("authorization")) and _wants_html(request):
        return HTMLResponse(web_pages.me_page(), status_code=200)
    if not extract_bearer_key(request.headers.get("authorization")):
        raise HTTPException(
            status_code=401,
            detail="Sign in or send `Authorization: Bearer wa_live_...`.",
            headers={"WWW-Authenticate": oauth.www_authenticate_challenge()},
        )
    try:
        record = await asyncio.to_thread(identity.resolve_bearer, request.headers.get("authorization"))
    except GateError as exc:
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = oauth.www_authenticate_challenge()
        raise HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers) from exc
    if not record:
        raise HTTPException(
            status_code=401,
            detail="Sign in or send `Authorization: Bearer wa_live_...`.",
            headers={"WWW-Authenticate": oauth.www_authenticate_challenge()},
        )
    return {
        "status": record.get("status"),
        "plan": record.get("plan"),
        "email": record.get("email", ""),
        "auth_type": record.get("auth_type"),
        "pro_active": record.get("pro_active"),
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
REPO_URL = "https://github.com/WarreAndVavasour/WorkspaceAlberta"


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
        elif tool.name in SIGN_IN_TOOLS:
            tags.append("sign-in")
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
                "Public tools work anonymously. Saved profiles require free OAuth sign-in. "
                "Pro tools additionally require an active subscription. "
                "OAuth access tokens and legacy wa_live_ keys use Authorization: Bearer."
            ),
        },
        "securitySchemes": {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "OAuth access token or legacy subscriber key for protected tools.",
            }
        },
        "security": [{}, {"bearer": []}],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["text/markdown"],
        "skills": skills,
        "x-workspacealberta": workflow_contract(),
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
@app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
async def oauth_protected_resource() -> JSONResponse:
    """RFC 9728 protected-resource metadata for the MCP endpoint.

    ``resource`` is the canonical public MCP URL, not ``request.base_url``,
    because Claude requires an exact match with the URL users paste and
    Cloud Run sees the internal ``*.run.app`` host behind Cloudflare.
    """
    return JSONResponse(oauth.protected_resource_metadata())


@app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def oauth_authorization_server() -> JSONResponse:
    """RFC 8414 metadata for the in-process workspaceAlberta authorization server."""
    return JSONResponse(oauth.authorization_server_metadata())


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
                "workspaceAlberta reads every CanadaBuys and Alberta "
                "Purchasing Connection notice and ranks them for any business."
            ),
            "version": app.version,
            "repository": {"url": REPO_URL, "source": "github"},
            "remotes": [{"type": "streamable-http", "url": f"{base}/mcp"}],
        }
    )


@app.post("/stripe/webhook", tags=["billing"], include_in_schema=False)
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
    if result.get("provisioned"):
        telemetry.capture("subscription_started", properties={"plan": "pro", **telemetry.WEBHOOK_CALLER})
    elif result.get("revoked"):
        telemetry.capture("subscription_cancelled", properties={"plan": "pro", **telemetry.WEBHOOK_CALLER})
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
    return await run_tool(tool_name, arguments, _auth(request), _rest_caller(request))


@app.post("/search", tags=["procurement"])
async def search(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Search CanadaBuys and Alberta Purchasing Connection together."""
    return await run_tool("search_opportunities", arguments, _auth(request), _rest_caller(request))


@app.get("/details/{reference}", tags=["procurement"])
async def details(reference: str, request: Request) -> dict[str, Any]:
    """Get details for a CanadaBuys or Alberta APC opportunity."""
    return await run_tool("get_opportunity_details", {"reference": reference}, _auth(request), _rest_caller(request))


@app.post("/deadlines", tags=["procurement"])
async def deadlines(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """List federal and Alberta opportunities closing soon."""
    return await run_tool("list_deadlines", arguments, _auth(request), _rest_caller(request))


@app.post("/matches", tags=["procurement"])
async def matches(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Rank opportunities against the saved business profile."""
    return await run_tool("find_matching_opportunities", arguments, _auth(request), _rest_caller(request))


@app.post("/brief", tags=["procurement"])
async def brief(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Generate the daily bid brief."""
    return await run_tool("daily_bid_brief", arguments, _auth(request), _rest_caller(request))


@app.post("/industrial-programs", tags=["procurement"])
async def industrial_programs(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Match a business to the read-only industrial and tariff support catalog."""
    return await run_tool("match_industrial_support_programs", arguments, _auth(request), _rest_caller(request))


@app.post("/bid-room/process", tags=["bid-room"])
async def bid_room_process(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Process a bid room in E2B and analyze it with Cohere inside the sandbox.

    Pro-gated: requires a valid subscriber Bearer key when the gate is on.
    """
    try:
        record = await asyncio.to_thread(check_tool_access, "process_bid_room", _auth(request))
    except GateError as exc:
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = oauth.www_authenticate_challenge()
        raise HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers) from exc

    token = storage.set_tenant(tenant_id_for(record)) if record else None
    try:
        return await process_bid_room_artifact_bounded(arguments or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if token is not None:
            storage.reset_tenant(token)


@app.post("/bid-room/classify", tags=["bid-room"])
async def bid_room_classify(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """List the bidder requirements in a tender package (TypeSafe Jev classification).

    Pro-gated like ``/bid-room/process``. Returns the artifact envelope, or the private
    upload link for an APC reference called without ``upload_token``.
    """
    try:
        record = await asyncio.to_thread(check_tool_access, "classify_tender", _auth(request))
    except GateError as exc:
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = oauth.www_authenticate_challenge()
        raise HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers) from exc

    token = storage.set_tenant(tenant_id_for(record)) if record else None
    try:
        return await classify_tender_artifact_bounded(arguments or {})
    except ClassifierNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    return await run_tool("set_business_profile", arguments, _auth(request), _rest_caller(request))


@app.get("/profile", tags=["profile"])
async def get_profile(request: Request) -> dict[str, Any]:
    """Return the saved business profile."""
    return await run_tool("get_my_profile", {}, _auth(request), _rest_caller(request))


@app.post("/cohere/analyze", tags=["analysis"])
async def cohere_analyze(request: Request, arguments: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Analyze a CanadaBuys tender with Cohere Command A+ when configured."""
    return await run_tool("analyze_contract_with_cohere", arguments, _auth(request), _rest_caller(request))


# ---------------------------------------------------------------------------
# Browser-facing errors and /docs request examples.
# ---------------------------------------------------------------------------

_HTML_ERROR_COPY = {
    400: ("This link is not complete", "Something in this address is missing or wrong."),
    401: ("Sign-in happens in your AI app", "You do not need to sign in on this website. Your AI app asks you to sign in when you use a Pro feature."),
    403: ("This page is not available", "You do not have access to this page."),
    404: ("Page not found", "We could not find that page. It may have moved, or the address may have a typo."),
    410: ("This link has expired", "This link is no longer valid. Start again from your AI app."),
}


@app.exception_handler(StarletteHTTPException)
async def html_friendly_http_errors(request: Request, exc: StarletteHTTPException):
    """People navigating in a browser get a readable page; API clients keep JSON."""
    if _wants_html(request) and exc.status_code in _HTML_ERROR_COPY:
        heading, message = _HTML_ERROR_COPY[exc.status_code]
        detail = exc.detail if isinstance(exc.detail, str) and exc.status_code != 404 else ""
        if exc.status_code == 401:
            detail = ""
        return HTMLResponse(
            web_pages.message_page(heading, heading, message, status_hint=detail),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )
    from fastapi.exception_handlers import http_exception_handler

    return await http_exception_handler(request, exc)


_EXAMPLE_PROFILE = {"description": "Concrete and excavation contractor", "location": "Calgary, Alberta"}
_DOCS_EXAMPLES = {
    "/search": ("search_opportunities", {"keywords": "concrete", "source": "all", "limit": 10}),
    "/deadlines": ("list_deadlines", {"days": 14, "source": "alberta", "limit": 10}),
    "/matches": ("find_matching_opportunities", {"profile": _EXAMPLE_PROFILE, "days": 60, "limit": 10}),
    "/brief": ("daily_bid_brief", {"profile": _EXAMPLE_PROFILE, "days": 14}),
    "/industrial-programs": (
        "match_industrial_support_programs",
        {"description": "Steel fabrication and welding", "location": "Edmonton, Alberta"},
    ),
    "/profile": ("set_business_profile", {"company_name": "Example Concrete Ltd", **_EXAMPLE_PROFILE}),
}


def _openapi_with_examples() -> dict[str, Any]:
    """Show each REST body's real fields and a working example in /docs."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=app.title, version=app.version, description=app.description,
                         routes=app.routes, tags=app.openapi_tags)
    for path, (tool_name, example) in _DOCS_EXAMPLES.items():
        operation = schema.get("paths", {}).get(path, {}).get("post")
        tool_schema = _tool_schema(tool_name)
        if not operation or not tool_schema:
            continue
        body_schema = dict(tool_schema)
        operation["requestBody"] = {
            "required": False,
            "content": {"application/json": {"schema": body_schema, "example": example}},
        }
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_examples  # type: ignore[method-assign]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
