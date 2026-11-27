"""Server-side PostHog telemetry and MCP Analytics for the hosted procurement endpoint.

Only the hosted adapter (``server_http.py``) emits events — the stdio server
and self-hosted installs never phone home.

MCP protocol traffic on ``/mcp`` is instrumented with the official PostHog MCP
Analytics SDK (``posthog.mcp``), emitting:

- ``$mcp_tool_call``           every MCP ``tools/call`` (tool name, duration,
                               intent, model, session, declared input keys,
                               and error diagnostics)
- ``$mcp_initialize``          every MCP ``initialize`` handshake
- ``$mcp_tools_list``          every MCP ``tools/list`` discovery request
- ``$mcp_feedback``            agent feedback via ``send_feedback`` or
                               ``submit_feedback``
- ``$mcp_missing_capability``  missing-tool reports via ``get_more_tools``
- ``$exception``               sibling error-tracking event on failed tool calls

Web, REST, gate, and Stripe funnel moments continue to use the ``object_action``
snake_case taxonomy:

- ``tool_called``              REST tool calls (``transport="rest"``)
- ``pro_tool_denied``          a protected/Pro tool was called without access
- ``landing_page_viewed``      a browser opened ``/``
- ``endpoint_root_hit``        anything else (MCP client, crawler, script) hit ``/``
- ``subscription_started``     Stripe webhook provisioned a subscriber
- ``subscription_cancelled``   Stripe webhook revoked a subscriber

Caller identity (see :func:`caller_context`): request events carry
``client_name`` / ``client_version`` (MCP ``clientInfo``; ``"rest"`` for REST),
``protocol_version``, ``mcp_session_id_hash`` (salted hash, never the raw id),
``ua_family``, ``is_internal`` and the caller's address as ``$ip``.

The hosted transport is stateless, so the server keeps no session table.
``PostHogMcpStatelessSessionMiddleware`` mints an ``Mcp-Session-Id`` token on
``initialize`` carrying the derived ``ses_...`` session id and client metadata;
clients echo it on later requests so any Cloud Run instance correlates the
session. Legacy ``wa1.<payload>.<signature>`` session headers (:func:`mint_session_id`)
remain readable for backward compatibility. Clients on the 2026 protocol send
``clientInfo`` in each request's ``_meta`` and echo ``conversation_id``.

``$ip`` is ``CF-Connecting-IP`` only when the connecting peer (the right-most
``X-Forwarded-For`` entry, appended by Cloud Run) is inside Cloudflare's
published ranges. The custom domain is the ``elbows-mcp`` Worker, which passes
the visitor's request headers on to Cloud Run; a Cloudflare address in
``CF-Connecting-IP`` (a Worker's own egress) is not a visitor and is dropped.
Direct ``run.app`` requests use the right-most ``X-Forwarded-For`` entry, since
everything left of it is client-supplied. ``ip_source`` records which rule
applied. PostHog turns ``$ip`` into GeoIP properties; with no usable address
``$geoip_disable`` is set.

Privacy stance: ``before_send`` strips ``$mcp_parameters`` and ``$mcp_response``
so no tool request bodies, inline business profiles, upload tokens, or tender
analysis outputs leave the server. Emails and raw session headers are never sent.
Events are sent person-less (``process_person_profile: false``) so PostHog never
builds person records.

Cloud Logging: independently of PostHog, every tool call and gate denial
also writes one JSON line to stdout (``"event": "mcp_tool_call"`` /
``"mcp_gate_denied"``). Cloud Run ingests it as ``jsonPayload`` and the
``wa_tool_calls`` / ``wa_tool_latency`` log-based metrics read it for the
"WorkspaceAlberta - MCP Usage" dashboard.

``submit_feedback`` and ``send_feedback`` are the review-log exception: their
``mcp_feedback`` Cloud Logging line includes the secret-redacted report so a
person can review it.

Environment variables:
    WA_TOOL_LOG           set to "0" to turn the stdout tool-call line off
    POSTHOG_API_KEY       project API key (phc_...); telemetry is off without it
                          (POSTHOG_PROJECT_TOKEN is also accepted)
    POSTHOG_HOST          ingestion host, default https://us.i.posthog.com
    WA_ENVIRONMENT        environment tag on every event, default "prod"
    WA_SERVER_BUILD       immutable deployment build/revision id (falls back to
                          GIT_SHA or Cloud Run's K_REVISION)
    WA_TELEMETRY_SALT     key for session-id signing and hashing; defaults to a
                          key derived from WA_OAUTH_SIGNING_KEY (random per
                          process when neither is set, as in local runs)
    WA_INTERNAL_CLIENTS   comma-separated client names / user-agent prefixes
                          marked ``is_internal`` (adds to the built-in list)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import queue
import secrets
import sys
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_HOST = "https://us.i.posthog.com"
QUEUE_MAX_EVENTS = 1000
POST_TIMEOUT_SECONDS = 5
_MCP_CALL_META_SCOPE_KEY = "wa_mcp_call_meta"

_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_EVENTS)
_worker_lock = threading.Lock()
_worker: threading.Thread | None = None


def api_key() -> str:
    for env_name in ("POSTHOG_API_KEY", "POSTHOG_PROJECT_TOKEN", "POSTHOG_PROJECT_KEY"):
        candidate = os.environ.get(env_name, "").strip()
        # Personal API keys (phx_...) are query credentials, never ingestion tokens.
        if candidate and not candidate.startswith("phx_"):
            return candidate
    return ""


def host() -> str:
    return os.environ.get("POSTHOG_HOST", "").strip().rstrip("/") or DEFAULT_HOST


def enabled() -> bool:
    return bool(api_key())


def environment() -> str:
    return os.environ.get("WA_ENVIRONMENT", "").strip() or "prod"


def server_build() -> str | None:
    for env_name in ("WA_SERVER_BUILD", "GIT_SHA", "K_REVISION"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value[:256]
    return None


def tool_log_enabled() -> bool:
    return os.environ.get("WA_TOOL_LOG", "").strip() != "0"


def log_structured(entry: dict[str, Any]) -> bool:
    """Write one Cloud Logging-compatible JSON line to stdout. Never raises."""
    if not tool_log_enabled():
        return False
    try:
        sys.stdout.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")
        sys.stdout.flush()
    except Exception:
        return False
    return True


def _log_user(record: dict[str, Any] | None) -> str:
    """Pseudonymous metric label: the truncated hash id, or ``anon``."""
    uid = _distinct_id(record)
    return "anon" if uid == "anonymous" else uid


def _tier(record: dict[str, Any] | None) -> str:
    if not record:
        return "anon"
    return "pro" if record.get("pro_active") else "free"


def capture(
    event: str,
    distinct_id: str = "server",
    properties: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
) -> bool:
    """Queue one custom event. Returns True when accepted, False when off/full.

    ``caller`` is :func:`caller_context` for the request; its properties are
    added and, when ``distinct_id`` is left at the default, it chooses one.
    """
    if not enabled():
        return False
    if caller and distinct_id == "server":
        distinct_id = distinct_id_for(None, caller)
    payload = {
        "event": event,
        "distinct_id": distinct_id or "anonymous",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "properties": {
            "environment": environment(),
            "server": "workspacealberta-procurement",
            # Person-less: counts and funnels without person records.
            "$process_person_profile": False,
            **caller_properties(caller),
            **(properties or {}),
        },
    }
    return _dispatch(payload)


def _is_error_text(result_text: str) -> bool:
    from procurement_core.service import is_tool_error_text

    return is_tool_error_text(result_text)


def _write_tool_call_log(
    tool: str,
    transport: str,
    record: dict[str, Any] | None,
    arguments: dict[str, Any] | None,
    result_text: str,
    latency_ms: int,
    upstream: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    args = arguments or {}
    ok = not _is_error_text(result_text)
    entry: dict[str, Any] = {
        "severity": "INFO" if ok else "WARNING",
        "message": f"mcp_tool_call {tool} ok={ok} {latency_ms}ms",
        "event": "mcp_tool_call",
        "tool": tool,
        "transport": transport,
        "user": _log_user(record),
        "tier": _tier(record),
        "client_name": (caller or {}).get("client_name", ""),
        "is_internal": bool((caller or {}).get("is_internal")),
        "plan": (record or {}).get("plan", ""),
        "ok": ok,
        "duration_ms": latency_ms,
        "environment": environment(),
    }
    reference = _reference(args)
    if reference:
        entry["reference"] = reference
    if upstream:
        entry.update(upstream)
    log_structured(entry)
    return ok, reference


def capture_tool_call(
    tool: str,
    transport: str,
    record: dict[str, Any] | None,
    arguments: dict[str, Any] | None,
    result_text: str,
    latency_ms: int,
    upstream: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
) -> bool:
    """Emit ``tool_called`` for one REST/direct tool invocation and log to stdout."""
    args = arguments or {}
    ok, _ = _write_tool_call_log(
        tool, transport, record, args, result_text, latency_ms, upstream=upstream, caller=caller
    )
    return capture(
        "tool_called",
        distinct_id=distinct_id_for(record, caller),
        caller=caller,
        properties={
            "tool": tool,
            "transport": transport,
            "source": "agent",
            "authenticated": record is not None,
            "plan": (record or {}).get("plan", ""),
            "success": ok,
            "latency_ms": latency_ms,
            # Anonymous callers describing their business inline is the
            # activation signal in the funnel; the profile itself is not sent.
            "has_inline_profile": bool(args.get("profile")),
            "typesafe_est_usd": (upstream or {}).get("typesafe_est_usd", 0),
        },
    )


def classify_mcp_error_type(
    tool: str,
    result_text: str,
    known_tools: set[str] | frozenset[str] | None = None,
) -> str:
    """Map a failed tool result to PostHog MCP Analytics's semantic error buckets."""
    if known_tools is not None and tool not in known_tools:
        return "unknown_tool"
    lowered = (result_text or "").lower()
    if "unknown tool" in lowered:
        return "unknown_tool"
    if "temporarily limited" in lowered or "rate limit" in lowered:
        return "rate_limited"
    if "timed out" in lowered or "no completed analysis" in lowered or "timeout" in lowered:
        return "timeout"
    if lowered.startswith(("please provide ", "please describe ")) or any(
        token in lowered for token in ("required", "must be", "invalid", "unknown field", "too long", "at most")
    ):
        return "validation"
    if lowered.startswith("contract not found:"):
        return "api_4xx"
    if lowered.startswith((
        "cohere analysis is not available:",
        "alberta opportunity not available:",
        "alberta deadline search failed:",
        "alberta apc summary failed:",
    )):
        return "api_5xx"
    return "internal"


def set_mcp_call_context(
    ctx: Any,
    *,
    record: dict[str, Any] | None = None,
    arguments: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
    upstream: dict[str, Any] | None = None,
    error_type: str | None = None,
    error_status: int | None = None,
) -> None:
    """Attach per-call metadata to the ASGI request scope for ``posthog.mcp`` hooks."""
    request = getattr(ctx, "request", None)
    scope = getattr(request, "scope", None)
    if not isinstance(scope, dict):
        return
    args = arguments if isinstance(arguments, dict) else {}
    distinct_id = _distinct_id(record)
    meta: dict[str, Any] = {
        "authenticated": record is not None,
        "plan": (record or {}).get("plan", ""),
        "has_inline_profile": bool(args.get("profile")),
        "typesafe_est_usd": (upstream or {}).get("typesafe_est_usd", 0),
    }
    reference = _reference(args)
    if reference:
        meta["reference"] = reference
    if distinct_id != "anonymous":
        meta["distinct_id"] = distinct_id
    if caller is not None:
        meta["caller"] = caller
    if error_type:
        meta["error_type"] = error_type
    if error_status is not None:
        meta["error_status"] = error_status
    scope[_MCP_CALL_META_SCOPE_KEY] = meta


def log_mcp_tool_call(
    tool: str,
    record: dict[str, Any] | None,
    arguments: dict[str, Any] | None,
    result_text: str,
    latency_ms: int,
    *,
    upstream: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
    ctx: Any = None,
    known_tools: set[str] | frozenset[str] | None = None,
) -> bool:
    """Write the Cloud Logging stdout line and enrich the active PostHog MCP event.

    PostHog delivery for ``/mcp`` is handled by ``posthog.mcp.instrument``
    (``$mcp_tool_call`` + ``$exception``), avoiding duplicate ``tool_called`` rows.
    """
    ok, _ = _write_tool_call_log(
        tool, "mcp", record, arguments, result_text, latency_ms, upstream=upstream, caller=caller
    )
    error_type = None if ok else classify_mcp_error_type(tool, result_text, known_tools)
    set_mcp_call_context(
        ctx,
        record=record,
        arguments=arguments,
        caller=caller,
        upstream=upstream,
        error_type=error_type,
    )
    return ok


def _reference(args: dict[str, Any]) -> str:
    """The public posting reference named in the arguments, if any (max 80 chars)."""
    value = args.get("reference") if isinstance(args, dict) else None
    if not isinstance(value, (str, int)):
        return ""
    return str(value).strip()[:80]


def capture_gate_denied(
    tool: str, transport: str, status_code: int, caller: dict[str, Any] | None = None
) -> bool:
    """Emit ``pro_tool_denied`` — the paywall-hit funnel moment."""
    log_structured({
        "severity": "NOTICE",
        "message": f"mcp_gate_denied {tool} status={status_code}",
        "event": "mcp_gate_denied",
        "tool": tool,
        "transport": transport,
        "status_code": status_code,
        "client_name": (caller or {}).get("client_name", ""),
        "environment": environment(),
    })
    return capture(
        "pro_tool_denied",
        distinct_id=distinct_id_for(None, caller),
        caller=caller,
        properties={
            "tool": tool,
            "transport": transport,
            "source": "agent",
            "status_code": status_code,
        },
    )


def _distinct_id(record: dict[str, Any] | None) -> str:
    if not record:
        return "anonymous"
    if record.get("user_id"):
        user_id = str(record["user_id"])
        if "@" in user_id:
            # Never an email in an event: hash it like a key.
            user_id = hashlib.sha256(user_id.strip().lower().encode("utf-8")).hexdigest()
        return f"user_{user_id[:16]}"
    if record.get("key_hash"):
        return f"sub_{str(record['key_hash'])[:16]}"
    return "anonymous"


def distinct_id_for(record: dict[str, Any] | None, caller: dict[str, Any] | None) -> str:
    """Signed-in callers keep their account id; anonymous MCP sessions get
    ``anon:<mcp_session_id_hash>``; anything else is ``"anonymous"``."""
    signed_in = _distinct_id(record)
    if signed_in != "anonymous":
        return signed_in
    session_hash = (caller or {}).get("mcp_session_id_hash")
    return f"anon:{session_hash}" if session_hash else "anonymous"


# ---------------------------------------------------------------------------
# Caller identity: which client, from where, in which session.
# ---------------------------------------------------------------------------

SESSION_PREFIX = "wa1"
MAX_FIELD = 80
MAX_USER_AGENT = 200

# https://www.cloudflare.com/ips/ (checked 2026-10-26). Only a peer inside
# these ranges is trusted to set CF-Connecting-IP.
CLOUDFLARE_NETWORKS = tuple(ipaddress.ip_network(net) for net in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
    "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
))

# Our own scripts and harnesses (client name or user-agent prefix, lowercase).
INTERNAL_CLIENTS = (
    "wv-harness",
    "workspacealberta-acceptance",
    "workspacealberta-openai-readiness",
    "workspacealberta-readiness",
    "workspacealberta-demo",
    "oauth-readiness",
    "wa-demo",
)

# Stripe webhooks are server-to-server: the caller is Stripe, not a client.
WEBHOOK_CALLER = {"client_name": "stripe-webhook", "is_internal": False, "$geoip_disable": True}

_salt_lock = threading.Lock()
_random_salt: bytes | None = None


def _salt() -> bytes:
    """Key for session-id signing and hashing, stable across instances in prod."""
    explicit = os.environ.get("WA_TELEMETRY_SALT", "").strip()
    if explicit:
        return explicit.encode("utf-8")
    oauth_key = os.environ.get("WA_OAUTH_SIGNING_KEY", "").strip()
    if oauth_key:
        return hmac.new(oauth_key.encode("utf-8"), b"wa-telemetry-session-v1", hashlib.sha256).digest()
    global _random_salt
    with _salt_lock:
        if _random_salt is None:
            _random_salt = secrets.token_bytes(32)
        return _random_salt


def _clean(value: Any, limit: int = MAX_FIELD) -> str:
    if not isinstance(value, (str, int, float)):
        return ""
    return "".join(ch for ch in str(value) if ch.isprintable()).strip()[:limit]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(body: str) -> str:
    return _b64(hmac.new(_salt(), body.encode("ascii"), hashlib.sha256).digest()[:16])


def mint_session_id(client_name: Any, client_version: Any, protocol_version: Any) -> str:
    """A fresh ``Mcp-Session-Id`` that records the client's ``initialize``.

    Format ``wa1.<payload>.<signature>``: printable ASCII, as the transport
    spec requires, and readable by any instance holding the same key.
    """
    record = {
        "n": _clean(client_name),
        "v": _clean(client_version),
        "p": _clean(protocol_version, 32),
        "r": _b64(secrets.token_bytes(12)),
    }
    body = f"{SESSION_PREFIX}.{_b64(json.dumps(record, separators=(',', ':')).encode('utf-8'))}"
    return f"{body}.{_sign(body)}"


def read_session_id(session_id: str | None) -> dict[str, str]:
    """Client fields from a session id we minted; ``{}`` for anything else."""
    if not session_id or len(session_id) > 512:
        return {}
    parts = session_id.split(".")
    if len(parts) != 3 or parts[0] != SESSION_PREFIX:
        return {}
    body = f"{parts[0]}.{parts[1]}"
    if not hmac.compare_digest(_sign(body), parts[2]):
        return {}
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        record = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(record, dict):
        return {}
    return {
        "client_name": _clean(record.get("n")),
        "client_version": _clean(record.get("v")),
        "protocol_version": _clean(record.get("p"), 32),
    }


def read_posthog_session_token(session_id: str | None) -> dict[str, str]:
    """Client fields from a PostHog stateless ``Mcp-Session-Id`` token; ``{}`` otherwise."""
    if not session_id:
        return {}
    try:
        from posthog.mcp import decode_session_id
    except ImportError:
        return {}
    decoded = decode_session_id(session_id)
    if decoded is None:
        return {}
    return {
        "client_name": _clean(decoded.client_name),
        "client_version": _clean(decoded.client_version),
        "protocol_version": _clean(decoded.protocol_version, 32),
    }


def session_hash(session_id: str | None) -> str:
    """Salted, truncated hash of an ``Mcp-Session-Id``; never the raw id."""
    if not session_id:
        return ""
    return hmac.new(_salt(), session_id.encode("utf-8", "replace"), hashlib.sha256).hexdigest()[:16]


def _parse_ip(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:  # [v6]:port
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1:  # v4:port
        candidate = candidate.split(":", 1)[0]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_cloudflare(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(address in net for net in CLOUDFLARE_NETWORKS)


def _public(address: ipaddress.IPv4Address | ipaddress.IPv6Address | None) -> str:
    return str(address) if address is not None and address.is_global else ""


def client_ip(headers: Mapping[str, str], peer: str | None = None) -> tuple[str, str]:
    """``(ip, source)`` for the real caller; ``("", "none")`` when unknown.

    Cloud Run appends the address that connected to it as the right-most
    ``X-Forwarded-For`` entry; everything left of it is client-supplied. When
    that peer is Cloudflare, the visitor is in ``CF-Connecting-IP`` (our
    Worker forwards the visitor's headers unchanged). Without
    ``X-Forwarded-For`` (local runs) the socket peer plays the same role.
    """
    forwarded = [part.strip() for part in (headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    hop = _parse_ip(forwarded[-1]) if forwarded else _parse_ip(peer)
    if hop is None:
        return "", "none"
    if _is_cloudflare(hop):
        visitor_ip = _parse_ip(headers.get("cf-connecting-ip"))
        # A Cloudflare address here is a Worker's own egress, not a visitor.
        visitor = "" if visitor_ip is None or _is_cloudflare(visitor_ip) else _public(visitor_ip)
        return (visitor, "cf-connecting-ip") if visitor else ("", "none")
    address = _public(hop)
    return (address, "x-forwarded-for" if forwarded else "peer") if address else ("", "none")


def ua_family(user_agent: str | None, client_name: str | None = None) -> str:
    """browser / claude / chatgpt / cursor / vscode / other client / bot."""
    text = f"{client_name or ''} {user_agent or ''}".lower()
    if any(token in text for token in (
        "bot", "crawler", "spider", "slurp", "scanner", "facebookexternalhit", "headlesschrome",
    )):
        return "bot"
    if "claude" in text or "anthropic" in text:
        return "claude"
    if "chatgpt" in text or "openai" in text:
        return "chatgpt"
    if "cursor" in text:
        return "cursor"
    if "vscode" in text or "visual studio code" in text or "copilot" in text:
        return "vscode"
    if not client_name and (user_agent or "").lower().startswith("mozilla/"):
        return "browser"
    return "other client"


def _internal_names() -> tuple[str, ...]:
    extra = os.environ.get("WA_INTERNAL_CLIENTS", "")
    return INTERNAL_CLIENTS + tuple(n.strip().lower() for n in extra.split(",") if n.strip())


def is_internal(client_name: str | None, user_agent: str | None) -> bool:
    """True for our own harness and scripts, by client name or user agent."""
    names = _internal_names()
    name = (client_name or "").strip().lower()
    agent = (user_agent or "").strip().lower()
    return any(name == n or name.startswith(n + "/") or agent.startswith(n) for n in names)


def caller_context(
    headers: Mapping[str, str],
    *,
    transport: str,
    peer: str | None = None,
    client_info: Mapping[str, Any] | None = None,
    protocol_version: str | None = None,
) -> dict[str, Any]:
    """Who called: client, version, protocol, session hash, address, UA family.

    ``headers`` must answer lowercase names (Starlette ``Headers`` or a dict).
    For MCP, client fields come from ``client_info`` (2026 protocol ``_meta``)
    or else from the signed ``Mcp-Session-Id`` (or PostHog's stateless token).
    REST is ``client_name="rest"``; ``transport="web"`` (page views) leaves it empty.
    """
    user_agent = _clean(headers.get("user-agent"), MAX_USER_AGENT)
    session_id = headers.get("mcp-session-id") or ""
    if transport in ("rest", "web"):
        # REST calls are "rest"; page views have no client name.
        client = {"client_name": "rest" if transport == "rest" else "", "client_version": "", "protocol_version": ""}
    elif client_info:
        client = {
            "client_name": _clean(client_info.get("name")),
            "client_version": _clean(client_info.get("version")),
            "protocol_version": _clean(protocol_version, 32),
        }
    elif session_id.startswith(f"{SESSION_PREFIX}."):
        client = read_session_id(session_id) or {
            "client_name": "", "client_version": "", "protocol_version": "",
        }
    else:
        client = read_session_id(session_id) or read_posthog_session_token(session_id) or {
            "client_name": "", "client_version": "", "protocol_version": "",
        }
    client["protocol_version"] = (
        client.get("protocol_version") or _clean(headers.get("mcp-protocol-version"), 32)
    )
    ip, ip_source = client_ip(headers, peer)
    name = client["client_name"]
    return {
        **client,
        "client_name": name or ("" if transport == "web" else "unknown"),
        "mcp_session_id_hash": session_hash(session_id) if transport == "mcp" else "",
        "user_agent": user_agent,
        "ua_family": ua_family(user_agent, "" if name == "rest" else name),
        "is_internal": is_internal(name, user_agent),
        "ip": ip,
        "ip_source": ip_source,
    }


def caller_properties(caller: dict[str, Any] | None) -> dict[str, Any]:
    """PostHog properties for a caller; ``{}`` when there is none."""
    if not caller:
        return {}
    props = {
        key: caller.get(key, "")
        for key in ("client_name", "client_version", "protocol_version", "mcp_session_id_hash",
                    "user_agent", "ua_family", "ip_source")
    }
    props["is_internal"] = bool(caller.get("is_internal"))
    if caller.get("ip"):
        props["$ip"] = caller["ip"]
    else:
        # No caller address: keep PostHog from geolocating our own server.
        props["$geoip_disable"] = True
    return props


# ---------------------------------------------------------------------------
# PostHog MCP Analytics SDK integration (``posthog.mcp``).
# ---------------------------------------------------------------------------

_STRIPPED_MCP_PAYLOAD_KEYS = ("$mcp_parameters", "$mcp_response")

_INTENT_LABELS: dict[str, str] = {
    "get_server_guide": "Read workspaceAlberta server guide and capabilities",
    "set_business_profile": "Save business profile for procurement matching",
    "get_my_profile": "Read saved business profile",
    "search_opportunities": "Search open federal and Alberta procurement opportunities",
    "get_opportunity_details": "Inspect procurement opportunity details",
    "list_deadlines": "Check upcoming procurement closing deadlines",
    "find_matching_opportunities": "Rank open procurement opportunities for business fit",
    "find_business_fit": "Classify supply fit across open procurement notices",
    "daily_bid_brief": "Generate daily procurement bid brief",
    "match_industrial_support_programs": "Match Canadian industrial support programs",
    "watch_opportunity": "Add procurement opportunity to watchlist",
    "list_watchlist": "View tracked procurement watchlist",
    "unwatch_opportunity": "Remove procurement opportunity from watchlist",
    "bid_no_bid_scorecard": "Run deterministic bid/no-bid scorecard",
    "get_buyer_award_history": "Check historical contract awards and past winners",
    "victory_garden_brief": "Generate Victory Garden industrial mobilization brief",
    "process_bid_room": "Process and review tender package in E2B bid room",
    "classify_tender": "Classify tender bidder requirements",
    "analyze_contract_with_cohere": "Analyze tender package with Cohere Command A+",
    "submit_feedback": "Submit agent feedback report",
}


class _PostHogSDKBridge:
    """Lazy, env-gated PostHog v8 client adapter for ``posthog.mcp.instrument``.

    - When ``POSTHOG_API_KEY`` is unset, ``capture()`` is a no-op and no worker
      threads or network sockets are opened.
    - When tests patch :func:`_dispatch`, events are routed to ``_dispatch`` in
      memory with zero network traffic.
    - In production, events are handed to a live :class:`posthog.mcp.PostHogMCP`
      client targeting :func:`host`.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client: Any = None
        self._config: tuple[str, str, str | None] | None = None

    def client(self) -> Any:
        key = api_key()
        if not key:
            return None
        try:
            from posthog.mcp import PostHogMCP
        except ImportError:
            return None
        cfg = (key, host(), server_build())
        with self._lock:
            if self._client is None or self._config != cfg:
                if self._client is not None:
                    try:
                        self._client.shutdown()
                    except Exception:
                        pass
                self._client = PostHogMCP(key, host=cfg[1], server_build=cfg[2])
                self._config = cfg
            return self._client

    def capture(
        self,
        event: str,
        *,
        distinct_id: str | None = None,
        properties: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        timestamp: Any = None,
        uuid: Any = None,
        **kwargs: Any,
    ) -> str | None:
        if not enabled():
            return None
        if _dispatch is not _default_dispatch:
            props = dict(properties or {})
            opts = dict(options or {})
            if "process_person_profile" in opts:
                props.setdefault("$process_person_profile", bool(opts["process_person_profile"]))
            ts = (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp or datetime.now(timezone.utc).isoformat())
            )
            payload: dict[str, Any] = {
                "event": event,
                "distinct_id": distinct_id or "anonymous",
                "timestamp": ts,
                "properties": props,
                "options": opts,
            }
            if uuid is not None:
                payload["uuid"] = str(uuid)
            _dispatch(payload)
            return str(uuid or "")
        live = self.client()
        if live is None:
            return None
        return live.capture(
            event,
            distinct_id=distinct_id or "anonymous",
            properties=properties,
            options=options,
            timestamp=timestamp,
            uuid=uuid,
            **kwargs,
        )

    def flush(self) -> None:
        with self._lock:
            live = self._client
        if live is not None:
            try:
                live.flush()
            except Exception:
                pass

    def shutdown(self) -> None:
        with self._lock:
            live, self._client, self._config = self._client, None, None
        if live is not None:
            try:
                live.shutdown()
            except Exception:
                pass


_sdk_bridge = _PostHogSDKBridge()
_mcp_analytics_handle: Any = None


def _extra_caller_and_meta(request_dict: Mapping[str, Any] | None, extra: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    from posthog.mcp import get_request_headers
    from posthog.mcp.request_headers import get_request

    http_request = get_request(extra)
    scope = getattr(http_request, "scope", None)
    meta = scope.get(_MCP_CALL_META_SCOPE_KEY) if isinstance(scope, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    if isinstance(meta.get("caller"), dict):
        return meta["caller"], meta

    headers = get_request_headers(extra) or {}
    client = getattr(http_request, "client", None)
    ctx = extra.get("ctx") if isinstance(extra, Mapping) else None
    client_info = None
    protocol_version = getattr(ctx, "protocol_version", None) if ctx is not None else None
    if isinstance(request_dict, Mapping) and request_dict.get("method") == "initialize":
        params = request_dict.get("params")
        if isinstance(params, Mapping):
            raw_info = params.get("clientInfo")
            if isinstance(raw_info, Mapping):
                client_info = raw_info
            if isinstance(params.get("protocolVersion"), str):
                protocol_version = params["protocolVersion"]
    caller = caller_context(
        headers,
        transport="mcp",
        peer=getattr(client, "host", None),
        client_info=client_info,
        protocol_version=protocol_version,
    )
    return caller, meta


def _identify_mcp_caller(request_dict: dict[str, Any], extra: Any) -> Any:
    """Identify signed-in OAuth callers locally with zero network round-trips."""
    from posthog.mcp import UserIdentity, get_request_headers

    headers = get_request_headers(extra) or {}
    auth_header = headers.get("authorization")
    if not auth_header:
        return None
    from procurement_core import auth, oauth

    token = auth.extract_bearer_key(auth_header)
    if not token or not token.startswith(oauth.ACCESS_PREFIX):
        return None
    try:
        claims = oauth.validate_access_token(token)
    except Exception:
        return None
    sub = str(claims.get("sub") or "").strip()
    if not sub:
        return None
    return UserIdentity(distinct_id=_distinct_id({"user_id": sub}))


def _infer_mcp_intent(request_dict: dict[str, Any], extra: Any) -> str | None:
    """Privacy-safe fallback intent when a client omits the ``context`` parameter."""
    params = request_dict.get("params") if isinstance(request_dict, Mapping) else None
    if not isinstance(params, Mapping):
        return None
    name = str(params.get("name") or "").strip()
    if not name:
        return None
    base = _INTENT_LABELS.get(name, f"Invoke {name}")
    args = params.get("arguments")
    if not isinstance(args, Mapping):
        return base
    qualifiers: list[str] = []
    ref = _reference(dict(args))
    if ref:
        qualifiers.append(f"ref {ref}")
    source = args.get("source")
    if isinstance(source, str) and source.strip().lower() in {"all", "federal", "alberta", "canadabuys", "apc"}:
        qualifiers.append(f"source={source.strip().lower()}")
    days = args.get("days")
    if isinstance(days, int) and not isinstance(days, bool) and 1 <= days <= 365:
        qualifiers.append(f"days={days}")
    return f"{base} ({', '.join(qualifiers)})" if qualifiers else base


def _mcp_event_properties(request_dict: dict[str, Any], extra: Any) -> dict[str, Any]:
    caller, meta = _extra_caller_and_meta(request_dict, extra)
    props: dict[str, Any] = {
        "environment": environment(),
        "server": "workspacealberta-procurement",
        **caller_properties(caller),
    }
    if meta:
        for key in ("authenticated", "plan", "has_inline_profile", "typesafe_est_usd", "reference"):
            if key in meta:
                props[key] = meta[key]
        if meta.get("distinct_id"):
            props["_wa_distinct_id"] = meta["distinct_id"]
        if meta.get("error_type"):
            props["$mcp_error_type"] = meta["error_type"]
        if meta.get("error_status") is not None:
            props["$mcp_error_status"] = meta["error_status"]
    return props


def _mcp_event_options(request_dict: dict[str, Any], extra: Any) -> dict[str, Any]:
    # Preserve WorkspaceAlberta's person-less telemetry guarantee.
    return {"process_person_profile": False}


def _before_send_mcp_event(capture_event: dict[str, Any]) -> dict[str, Any] | None:
    if not enabled():
        return None
    props = capture_event.get("properties")
    if isinstance(props, dict):
        for key in _STRIPPED_MCP_PAYLOAD_KEYS:
            props.pop(key, None)
        resolved_distinct_id = props.pop("_wa_distinct_id", None)
        if isinstance(resolved_distinct_id, str) and resolved_distinct_id:
            capture_event["distinct_id"] = resolved_distinct_id
    return capture_event


def _on_posthog_feedback(report: Any) -> None:
    from procurement_core.feedback import record_posthog_feedback

    record_posthog_feedback(report)


async def capture_submit_feedback_to_posthog(
    arguments: Mapping[str, Any] | None,
    *,
    record: dict[str, Any] | None = None,
    caller: dict[str, Any] | None = None,
    ctx: Any = None,
) -> bool:
    """Mirror a successful ``submit_feedback`` MCP call into PostHog as ``$mcp_feedback``."""
    if not enabled() or not isinstance(arguments, Mapping):
        return False
    try:
        from posthog.mcp import (
            FeedbackReport,
            decode_session_id,
            derive_session_id_from_mcp_session,
            get_request_headers,
        )
        from posthog.mcp._event_types import MCPAnalyticsEventType
        from posthog.mcp._sink import McpCaptureOptions, McpEventSink
        from posthog.mcp.feedback import build_feedback_event_properties, build_feedback_intent
        from posthog.mcp.version import __version__ as mcp_sdk_version
    except ImportError:
        return False

    category = str(arguments.get("category") or "other").strip()
    feedback_type = "missing_capability" if category == "missing_capability" else (
        "other" if category == "other" else "issue"
    )
    attempted = str(arguments.get("what_i_was_trying_to_do") or "").strip()
    problem = str(arguments.get("what_went_wrong") or "").strip()
    details = "\n\n".join(part for part in (attempted, problem) if part) or None
    report = FeedbackReport(
        feedback_type=feedback_type,
        summary=str(arguments.get("summary") or "").strip(),
        details=details,
        friction_points=problem or None,
        suggested_improvement=str(arguments.get("proposed_fix") or "").strip() or None,
        tool_name=str(arguments.get("tool_name") or "").strip() or None,
    )
    headers = get_request_headers(ctx) or {}
    raw_session = headers.get("mcp-session-id")
    decoded = decode_session_id(raw_session)
    session_id = (
        decoded.session_id
        if decoded is not None
        else (derive_session_id_from_mcp_session(raw_session) if raw_session else None)
    )
    distinct = _distinct_id(record)
    distinct_id = None if distinct == "anonymous" else distinct
    intent = build_feedback_intent(report)

    mcp_event: dict[str, Any] = {
        "event_type": MCPAnalyticsEventType.MCP_FEEDBACK,
        "session_id": session_id,
        "identify_actor_given_id": distinct_id,
        "sdk_language": "Python",
        "sdk_version": mcp_sdk_version,
        "server_name": "canadabuys",
        "server_version": "1.3.0",
        "server_build": server_build(),
        "resource_name": "submit_feedback",
        "client_name": (caller or {}).get("client_name") or None,
        "client_version": (caller or {}).get("client_version") or None,
        "protocol_version": (caller or {}).get("protocol_version") or None,
        "client_user_agent": (caller or {}).get("user_agent") or None,
        "vendor_client": headers.get("x-anthropic-client") or None,
        "user_intent": intent or None,
        "user_intent_source": "context_parameter" if intent else None,
        "properties": {
            "environment": environment(),
            "server": "workspacealberta-procurement",
            **caller_properties(caller),
            **build_feedback_event_properties(report),
        },
        "event_options": {"process_person_profile": False},
        "timestamp": datetime.now(timezone.utc),
    }
    sink = McpEventSink(_sdk_bridge)  # type: ignore[arg-type]
    await sink.capture(
        mcp_event,
        McpCaptureOptions(enable_exception_autocapture=True, before_send=_before_send_mcp_event),
    )
    return True


def instrument_mcp_server(
    mcp_server: Any,
    *,
    resolve_original_tool: Callable[[str], Any] | None = None,
) -> Any:
    """Wrap ``mcp_server`` with PostHog MCP Analytics, feedback, and missing-tool reporting."""
    global _mcp_analytics_handle
    try:
        from posthog.mcp import CollectFeedbackOptions, MCPAnalyticsOptions, instrument
    except ImportError:
        _mcp_analytics_handle = None
        return None
    _mcp_analytics_handle = instrument(
        mcp_server,
        _sdk_bridge,  # type: ignore[arg-type]
        MCPAnalyticsOptions(
            collect_feedback=CollectFeedbackOptions(on_feedback=_on_posthog_feedback),
            report_missing=True,
            context=True,
            intent_fallback=_infer_mcp_intent,
            capture_model=True,
            enable_conversation_id=True,
            enable_exception_autocapture=True,
            resolve_original_tool=resolve_original_tool,
            identify=_identify_mcp_caller,
            event_properties=_mcp_event_properties,
            event_options=_mcp_event_options,
            before_send=_before_send_mcp_event,
            server_build=server_build(),
        ),
    )
    return _mcp_analytics_handle


def wrap_mcp_http_handler(asgi_app: Any) -> Any:
    """Wrap the stateless StreamableHTTP handler with PostHog's session-token middleware."""
    try:
        from posthog.mcp import PostHogMcpStatelessSessionMiddleware
    except ImportError:
        return asgi_app
    return PostHogMcpStatelessSessionMiddleware(asgi_app)


async def shutdown_mcp_analytics() -> None:
    """Drain in-flight MCP analytics tasks and flush the PostHog client on shutdown."""
    if _mcp_analytics_handle is not None and enabled():
        try:
            await _mcp_analytics_handle.flush()
        except Exception:
            pass
    _sdk_bridge.shutdown()


def _default_dispatch(payload: dict[str, Any]) -> bool:
    _ensure_worker()
    try:
        _queue.put_nowait(payload)
    except queue.Full:
        return False
    return True


_dispatch = _default_dispatch


def _ensure_worker() -> None:
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_drain, name="posthog-telemetry", daemon=True)
            _worker.start()


def _drain() -> None:
    while True:
        payload = _queue.get()
        try:
            _post(payload)
        except Exception:
            # Telemetry never surfaces failures to callers.
            pass
        finally:
            _queue.task_done()


def _post(payload: dict[str, Any]) -> None:
    body = json.dumps({"api_key": api_key(), **payload}).encode("utf-8")
    request = Request(
        f"{host()}/capture/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=POST_TIMEOUT_SECONDS) as response:
        response.read()
