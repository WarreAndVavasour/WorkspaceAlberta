"""Server-side PostHog telemetry for the hosted procurement endpoint.

Only the hosted adapter (``server_http.py``) emits events — the stdio server
and self-hosted installs never phone home. Event names follow the
``object_action`` snake_case taxonomy in the operator's PostHog project:

- ``tool_called``          every MCP/REST tool call (tool, transport,
                           authenticated, plan, success, latency_ms,
                           has_inline_profile)
- ``pro_tool_denied``      a Pro tool was called without a valid key — the
                           "hit the paywall" funnel moment
- ``landing_page_viewed``  someone opened ``/`` in a browser
- ``subscription_started`` Stripe webhook provisioned a subscriber
- ``subscription_cancelled`` Stripe webhook revoked a subscriber

Privacy stance: no request bodies, no profile contents, no IPs. The
distinct_id is a truncated key hash for subscribers and the literal
``"anonymous"`` otherwise, and events are sent person-less
(``$process_person_profile: false``) so PostHog never builds person records.

Delivery is fire-and-forget: events go onto a bounded in-memory queue and a
daemon thread posts them with a short timeout. A full queue drops events and
a PostHog outage is invisible to callers — telemetry must never slow down or
break a tool call.

Environment variables:
    POSTHOG_API_KEY   project API key (phc_...); telemetry is off without it
    POSTHOG_HOST      ingestion host, default https://us.i.posthog.com
    WA_ENVIRONMENT    environment tag on every event, default "prod"
"""

from __future__ import annotations

import json
import os
import queue
import threading
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


def capture(event: str, distinct_id: str = "server", properties: dict[str, Any] | None = None) -> bool:
    """Queue one event. Returns True when accepted, False when off/full."""
    if not enabled():
        return False
    payload = {
        "event": event,
        "distinct_id": distinct_id or "anonymous",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "properties": {
            "environment": environment(),
            "server": "workspacealberta-procurement",
            # Person-less: counts and funnels without person records.
            "$process_person_profile": False,
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
) -> bool:
    """Emit ``tool_called`` for one MCP/REST tool invocation."""
    args = arguments or {}
    return capture(
        "tool_called",
        distinct_id=_distinct_id(record),
        properties={
            "tool": tool,
            "transport": transport,
            "source": "agent",
            "authenticated": record is not None,
            "plan": (record or {}).get("plan", ""),
            "success": not result_text.startswith("Error:"),
            "latency_ms": latency_ms,
            # Anonymous callers describing their business inline is the
            # activation signal in the funnel; the profile itself is not sent.
            "has_inline_profile": bool(args.get("profile")),
        },
    )


def capture_gate_denied(tool: str, transport: str, status_code: int) -> bool:
    """Emit ``pro_tool_denied`` — the paywall-hit funnel moment."""
    return capture(
        "pro_tool_denied",
        distinct_id="anonymous",
        properties={
            "tool": tool,
            "transport": transport,
            "source": "agent",
            "status_code": status_code,
        },
    )


def _distinct_id(record: dict[str, Any] | None) -> str:
    if record and record.get("key_hash"):
        return f"sub_{str(record['key_hash'])[:16]}"
    return "anonymous"


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
