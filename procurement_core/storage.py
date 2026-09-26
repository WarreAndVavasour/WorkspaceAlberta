"""Tenant-aware storage for business profiles and watchlists.

Single-tenant installs (stdio server, dev, self-hosted) keep the original
behaviour: JSON files in ``DATA_DIR``. The hosted multi-tenant server sets a
tenant context per request:

- OAuth users: ``user:<uuid>`` rows in ``wa_user_data``
- Legacy ``wa_live_`` keys: the subscriber's ``wa_subscribers`` row

Anonymous callers on the hosted endpoint do **not** share a file-backed
profile. They must pass an inline ``profile`` argument or sign in.

Wiring:

- ``server_http.py`` binds :func:`set_tenant` from the validated identity
  (or ``None`` for anonymous requests) using a ``contextvars.ContextVar``
  so concurrent requests can't leak into each other.
- ``service.load_profile``/``save_profile`` and
  ``extensions.load_watchlist``/``save_watchlist`` call
  :func:`get_json_field`/:func:`set_json_field` which pick the backend:
  Supabase when a tenant is set *and* Supabase is configured, local files
  only when :func:`allow_anonymous_file_persist` is true.

Failure stance matches the rest of the core: a Supabase outage degrades to
empty data, never a crash in a tool handler.
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_current_tenant: ContextVar[str | None] = ContextVar("wa_current_tenant", default=None)

TENANT_FIELDS = {"profile", "watchlist"}
USER_TENANT_PREFIX = "user:"


def is_hosted() -> bool:
    """True on the shared Cloud Run endpoint, where anonymous file I/O is unsafe.

    ``WA_HOSTED=1`` is the explicit flag. Cloud Run also sets ``K_SERVICE``;
    that is treated as hosted unless ``WA_HOSTED=0``.
    """
    flag = os.environ.get("WA_HOSTED", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return bool(os.environ.get("K_SERVICE", "").strip())


def allow_anonymous_file_persist() -> bool:
    """Local stdio/dev may use DATA_DIR/profile.json; the hosted app must not."""
    override = os.environ.get("WA_ANONYMOUS_FILE_PROFILE", "").strip().lower()
    if override in {"1", "true", "yes"}:
        return True
    if override in {"0", "false", "no"}:
        return False
    return not is_hosted()


def set_tenant(key_hash: str | None):
    """Bind the current request to a subscriber or signed-in user (or None)."""
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


def _is_user_tenant(tenant: str) -> bool:
    return tenant.startswith(USER_TENANT_PREFIX)


def get_json_field(field: str, default: Any) -> Any:
    """Read a tenant's JSON field (``profile`` or ``watchlist``).

    OAuth users read ``wa_user_data`` (keyed by user id). Legacy API-key
    subscribers still read the ``wa_subscribers`` row. Falls back to
    ``default`` when anonymous, unconfigured, missing, or on upstream failure.
    """
    if field not in TENANT_FIELDS:
        raise ValueError(f"Unknown tenant field: {field}")
    tenant = current_tenant()
    if not tenant or not _supabase_available():
        return None  # caller uses local-file path
    try:
        if _is_user_tenant(tenant):
            user_id = tenant[len(USER_TENANT_PREFIX) :]
            params = urlencode({"user_id": f"eq.{user_id}", "select": field, "limit": "1"})
            rows = _request("GET", f"wa_user_data?{params}")
        else:
            params = urlencode({"key_hash": f"eq.{tenant}", "select": field, "limit": "1"})
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
    try:
        if _is_user_tenant(tenant):
            user_id = tenant[len(USER_TENANT_PREFIX) :]
            existing_params = urlencode({"user_id": f"eq.{user_id}", "select": "user_id", "limit": "1"})
            existing = _request("GET", f"wa_user_data?{existing_params}") or []
            if existing:
                params = urlencode({"user_id": f"eq.{user_id}"})
                _request("PATCH", f"wa_user_data?{params}", {field: value})
            else:
                _request("POST", "wa_user_data", [{"user_id": user_id, field: value}])
        else:
            params = urlencode({"key_hash": f"eq.{tenant}"})
            _request("PATCH", f"wa_subscribers?{params}", {field: value})
    except (HTTPError, URLError, RuntimeError):
        # Swallow write failure into a False so the caller can warn; the
        # hosted server treats storage as best-effort per request.
        return False
    return True


def tenant_active() -> bool:
    """True when the current request is bound to a Supabase-backed tenant."""
    return bool(current_tenant() and _supabase_available())
