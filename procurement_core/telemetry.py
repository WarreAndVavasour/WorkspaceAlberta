"""Server-side PostHog telemetry for the hosted procurement endpoint.

Only the hosted adapter (``server_http.py``) emits events — the stdio server
and self-hosted installs never phone home. Event names follow the
``object_action`` snake_case taxonomy in the operator's PostHog project:

- ``tool_called``          every MCP/REST tool call (tool, transport,
                           authenticated, plan, success, latency_ms,
                           has_inline_profile)
- ``pro_tool_denied``      a Pro tool was called without a valid key — the
                           "hit the paywall" funnel moment
- ``landing_page_viewed``  a browser opened ``/``
- ``endpoint_root_hit``    anything else (MCP client, crawler, script) hit ``/``
- ``subscription_started`` Stripe webhook provisioned a subscriber
- ``subscription_cancelled`` Stripe webhook revoked a subscriber

Caller identity (see :func:`caller_context`): request events carry
``client_name`` / ``client_version`` (MCP ``clientInfo``; ``"rest"`` for REST),
``protocol_version``, ``mcp_session_id_hash`` (salted hash, never the raw id),
``ua_family``, ``is_internal`` and the caller's address as ``$ip``.

The hosted transport is stateless, so the server keeps no session table.
Instead ``initialize`` answers with an ``Mcp-Session-Id`` that is itself a
signed record of the client's name, version and protocol version
(:func:`mint_session_id`); clients send it back on every request, and any
instance can read it. Clients on the 2026 protocol send ``clientInfo`` in
each request's ``_meta`` instead, which is read directly.

``$ip`` is ``CF-Connecting-IP`` only when the connecting peer (the right-most
``X-Forwarded-For`` entry, appended by Cloud Run) is inside Cloudflare's
published ranges. The custom domain is the ``elbows-mcp`` Worker, which passes
the visitor's request headers on to Cloud Run; a Cloudflare address in
``CF-Connecting-IP`` (a Worker's own egress) is not a visitor and is dropped.
Direct ``run.app`` requests use the right-most ``X-Forwarded-For`` entry, since
everything left of it is client-supplied. ``ip_source`` records which rule
applied. PostHog turns ``$ip`` into GeoIP properties; with no usable address
``$geoip_disable`` is set (PostHog still stores the sending server's address
as ``$ip`` on those events, so filter on ``ip_source != 'none'``).

Privacy stance: no request bodies, no profile contents, no emails or raw
session ids. The distinct_id is a truncated account or key hash for signed-in
callers, ``anon:<mcp_session_id_hash>`` for anonymous MCP sessions and the
literal ``"anonymous"`` otherwise. Events are sent person-less
(``$process_person_profile: false``) so PostHog never builds person records.

Delivery is fire-and-forget: events go onto a bounded in-memory queue and a
daemon thread posts them with a short timeout. A full queue drops events and
a PostHog outage is invisible to callers — telemetry must never slow down or
break a tool call.

Cloud Logging: independently of PostHog, every tool call and gate denial
also writes one JSON line to stdout (``"event": "mcp_tool_call"`` /
``"mcp_gate_denied"``). Cloud Run ingests it as ``jsonPayload`` and the
``wa_tool_calls`` / ``wa_tool_latency`` log-based metrics read it for the
"WorkspaceAlberta - MCP Usage" dashboard. Same privacy stance: the user is
the truncated hash distinct_id, never an email, arguments or results.

Two additions on ``mcp_tool_call`` lines:

- ``upstream``: what the call used from paid APIs, as counts only (from
  :mod:`.usage`), e.g. ``{"typesafe": {"requests": 5712, "input_tokens":
  7.9e6}, "e2b": {"sandboxes": 1, "sandbox_seconds": 41.2}}``, plus
  ``typesafe_est_usd``. Omitted when the call used no paid API.
- ``reference``: the public tender reference the call was about, when the
  arguments name one. Posting references are public identifiers, not user
  data; they let a run of calls (search, details, classify) be read as one
  task. No other argument is logged.

Environment variables:
    WA_TOOL_LOG       set to "0" to turn the stdout tool-call line off
    POSTHOG_API_KEY   project API key (phc_...); telemetry is off without it
    POSTHOG_HOST      ingestion host, default https://us.i.posthog.com
    WA_ENVIRONMENT    environment tag on every event, default "prod"
    WA_TELEMETRY_SALT key for session-id signing and hashing; defaults to a
                      key derived from WA_OAUTH_SIGNING_KEY (random per
                      process when neither is set, as in local runs)
    WA_INTERNAL_CLIENTS comma-separated client names / user-agent prefixes
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
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_HOST = "https://us.i.posthog.com"
QUEUE_MAX_EVENTS = 1000
POST_TIMEOUT_SECONDS = 5

_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_EVENTS)
_worker_lock = threading.Lock()
_worker: threading.Thread | None = None


def api_key() -> str:
    return os.environ.get("POSTHOG_API_KEY", "").strip()


def host() -> str:
    return os.environ.get("POSTHOG_HOST", "").strip().rstrip("/") or DEFAULT_HOST


def enabled() -> bool:
    return bool(api_key())


def environment() -> str:
    return os.environ.get("WA_ENVIRONMENT", "").strip() or "prod"


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
    """Queue one event. Returns True when accepted, False when off/full.

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
    """Emit ``tool_called`` for one MCP/REST tool invocation.

    ``upstream`` is :meth:`usage.Meter.log_fields` for the call (paid-API counts).
    ``caller`` is :func:`caller_context` for the request.
    """
    args = arguments or {}
    ok = not result_text.startswith("Error:")
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
    or else from the signed ``Mcp-Session-Id``. REST is ``client_name="rest"``;
    ``transport="web"`` (page views) leaves it empty.
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
    else:
        client = read_session_id(session_id) or {
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


def _dispatch(payload: dict[str, Any]) -> bool:
    _ensure_worker()
    try:
        _queue.put_nowait(payload)
    except queue.Full:
        return False
    return True


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
