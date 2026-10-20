"""HTTP hardening for the hosted endpoint (NSA cyber hygiene / agentic AI guidance).

Three small controls, each safe to apply to every route:

- ``SecurityHeadersMiddleware`` adds baseline response headers to every
  response. A header that a route already set (for example the strict CSP on
  the OAuth sign-in pages) is kept as is.
- ``body_limit_bytes`` is the maximum size of one MCP JSON-RPC request body.
  File uploads use the separate bid-room upload route, so tool calls stay small.
- ``SlidingWindowLimiter`` limits how often one key (for example one email
  address) can do an action. It is in memory and per instance: it limits abuse
  from one client of one instance, and is not a replacement for an edge rate
  limit at Cloudflare.

``security_event`` writes one Cloud Logging JSON line for identity events
(client registration, token issue or denial, sign-in failure, consent). It
never logs emails, codes, tokens or secrets.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import deque
from typing import Any

from procurement_core import telemetry

DEFAULT_MCP_BODY_LIMIT = 4 * 1024 * 1024

# Values for headers that no route set itself.
BASELINE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    # No script-src: /docs loads Swagger UI from a CDN. These directives only
    # stop framing, <base> injection and plugins.
    (b"content-security-policy", b"frame-ancestors 'none'; base-uri 'self'; object-src 'none'"),
)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware, so streaming responses are not buffered."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                present = {key.lower() for key, _ in headers}
                for key, value in BASELINE_HEADERS:
                    if key not in present:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def body_limit_bytes() -> int:
    raw = os.environ.get("WA_MAX_MCP_BODY_BYTES", "").strip()
    try:
        value = int(raw) if raw else DEFAULT_MCP_BODY_LIMIT
    except ValueError:
        value = DEFAULT_MCP_BODY_LIMIT
    return value if value > 0 else DEFAULT_MCP_BODY_LIMIT


class BodyTooLarge(Exception):
    """The request body is larger than the configured limit."""


class SlidingWindowLimiter:
    """Allow at most ``limit`` events per ``window_seconds`` for each key."""

    def __init__(self, limit: int, window_seconds: float, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_keys:
                    self._evict(now)
                events = self._events[key] = deque()
            while events and now - events[0] >= self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def _evict(self, now: float) -> None:
        for key in [k for k, v in self._events.items() if not v or now - v[-1] >= self.window]:
            del self._events[key]
        while len(self._events) >= self.max_keys:
            self._events.pop(next(iter(self._events)))

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


def pseudonym(value: str) -> str:
    """Short one-way label for a client id or email, for log correlation only."""
    if not value:
        return ""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:12]


def security_event(event: str, *, severity: str = "NOTICE", **fields: Any) -> bool:
    """Write one ``security_event`` line to Cloud Logging. Never raises."""
    entry: dict[str, Any] = {
        "severity": severity,
        "message": f"security_event {event}",
        "event": "security_event",
        "kind": event,
        "environment": telemetry.environment(),
    }
    entry.update({key: value for key, value in fields.items() if value not in (None, "")})
    return telemetry.log_structured(entry)
