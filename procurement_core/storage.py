"""Tenant-aware storage for business profiles and watchlists.

Single-tenant installs (stdio server, dev, self-hosted) keep the original
behaviour: JSON files in ``DATA_DIR``. The hosted multi-tenant server sets a
tenant context per request (the authenticated subscriber's key hash), and
profile/watchlist reads and writes route to the ``wa_subscribers`` row in
Supabase instead.

Wiring:

- ``server_http.py`` middleware calls :func:`set_tenant` with the key hash
  from a validated Bearer key (or ``None`` for anonymous requests) — using a
  ``contextvars.ContextVar`` so concurrent requests can't leak into each
  other.
- ``service.load_profile``/``save_profile`` and
  ``extensions.load_watchlist``/``save_watchlist`` call
  :func:`get_json_field`/:func:`set_json_field` which pick the backend:
  Supabase when a tenant is set *and* Supabase is configured, local files
  otherwise.

Failure stance matches the rest of the core: a Supabase outage degrades to
empty data with the error captured in the row-fetch exception message, never
a crash in a tool handler.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_current_tenant: ContextVar[str | None] = ContextVar("wa_current_tenant", default=None)

TENANT_FIELDS = {"profile", "watchlist"}


def set_tenant(key_hash: str | None):
    """Bind the current request to a subscriber (or None for anonymous)."""
    return _current_tenant.set(key_hash)


def reset_tenant(token) -> None:
    """Restore the previous tenant binding (middleware cleanup)."""
    _current_tenant.reset(token)


def current_tenant() -> str | None:
    return _current_tenant.get()


def _supabase_available() -> bool:
    from procurement_core.auth import supabase_config

    url, key = supabase_config()
    return bool(url and key)


def _request(method: str, path_query: str, payload: dict | None = None) -> Any:
    from procurement_core.auth import supabase_config

    url, service_key = supabase_config()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{url}/rest/v1/{path_query}",
        data=data,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=minimal",
        },
        method=method,
    )
    with urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def get_json_field(field: str, default: Any) -> Any:
    """Read a tenant's JSON field (``profile`` or ``watchlist``).

    Falls back to ``default`` when anonymous, unconfigured, missing, or on
    upstream failure.
    """
    if field not in TENANT_FIELDS:
        raise ValueError(f"Unknown tenant field: {field}")
    tenant = current_tenant()
    if not tenant or not _supabase_available():
        return None  # caller uses local-file path
    params = urlencode({"key_hash": f"eq.{tenant}", "select": field, "limit": "1"})
    try:
        rows = _request("GET", f"wa_subscribers?{params}")
    except (HTTPError, URLError, json.JSONDecodeError, RuntimeError):
        return default
    if not rows:
        return default
    value = rows[0].get(field)
    return value if value is not None else default


def set_json_field(field: str, value: Any) -> bool:
    """Write a tenant's JSON field. Returns True when handled by Supabase."""
    if field not in TENANT_FIELDS:
        raise ValueError(f"Unknown tenant field: {field}")
    tenant = current_tenant()
    if not tenant or not _supabase_available():
        return False  # caller uses local-file path
    params = urlencode({"key_hash": f"eq.{tenant}"})
    try:
        _request("PATCH", f"wa_subscribers?{params}", {field: value})
    except (HTTPError, URLError, RuntimeError):
        # Swallow write failure into a False so the caller can warn; the
        # hosted server treats storage as best-effort per request.
        return False
    return True


def tenant_active() -> bool:
    """True when the current request is bound to a Supabase-backed tenant."""
    return bool(current_tenant() and _supabase_available())
