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
_current_tenant_record: ContextVar[dict[str, Any] | None] = ContextVar(
    "wa_current_tenant_record", default=None
)

# In-memory fallback credit ledger used when WA_OAUTH_STORE=memory or when
# Supabase is unavailable / migration 005 columns have not yet been applied.
_memory_credits: dict[str, dict[str, Any]] = {}

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


def set_tenant_record(record: dict[str, Any] | None):
    """Bind the validated identity record for the current request."""
    return _current_tenant_record.set(record)


def reset_tenant_record(token) -> None:
    """Restore the previous identity record binding."""
    _current_tenant_record.reset(token)


def current_tenant_record() -> dict[str, Any] | None:
    return _current_tenant_record.get()


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


# ============== Per-user Pro trial & Bid Pack credit ledger ==============


def _use_memory_credits() -> bool:
    if os.environ.get("WA_OAUTH_STORE", "").strip().lower() == "memory":
        return True
    return not _supabase_available()


def _default_credit_state() -> dict[str, Any]:
    return {
        "free_credits_used": 0,
        "paid_credits": 0,
        "stripe_customer_id": "",
        "credited_sessions": [],
    }


def clear_memory_credits() -> None:
    """Reset the in-memory credit ledger (used by tests)."""
    _memory_credits.clear()


def _normalize_credit_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = raw or {}
    sessions = data.get("credited_sessions")
    return {
        "free_credits_used": max(0, int(data.get("free_credits_used") or 0)),
        "paid_credits": max(0, int(data.get("paid_credits") or 0)),
        "stripe_customer_id": str(data.get("stripe_customer_id") or "").strip(),
        "credited_sessions": list(sessions) if isinstance(sessions, list) else [],
    }


def _read_supabase_credits(user_id: str) -> dict[str, Any] | None:
    params = urlencode(
        {
            "user_id": f"eq.{user_id}",
            "select": "free_credits_used,paid_credits,stripe_customer_id,credited_sessions",
            "limit": "1",
        }
    )
    try:
        rows = _request("GET", f"wa_user_data?{params}")
    except (HTTPError, URLError, json.JSONDecodeError, RuntimeError):
        return None
    if not rows:
        return _default_credit_state()
    return _normalize_credit_state(rows[0])


def _write_supabase_credits(user_id: str, state: dict[str, Any]) -> bool:
    payload = {
        "free_credits_used": max(0, int(state.get("free_credits_used") or 0)),
        "paid_credits": max(0, int(state.get("paid_credits") or 0)),
        "stripe_customer_id": str(state.get("stripe_customer_id") or "").strip(),
        "credited_sessions": list(state.get("credited_sessions") or [])[-50:],
    }
    try:
        existing_params = urlencode({"user_id": f"eq.{user_id}", "select": "user_id", "limit": "1"})
        existing = _request("GET", f"wa_user_data?{existing_params}") or []
        if existing:
            params = urlencode({"user_id": f"eq.{user_id}"})
            _request("PATCH", f"wa_user_data?{params}", payload)
        else:
            _request("POST", "wa_user_data", [{"user_id": user_id, **payload}])
        return True
    except (HTTPError, URLError, RuntimeError):
        return False


def get_user_credits(user_id: str) -> dict[str, Any]:
    """Read free-trial and Bid Pack credit state for an OAuth user."""
    uid = str(user_id or "").strip()
    if not uid:
        return _default_credit_state()
    if not _use_memory_credits():
        row = _read_supabase_credits(uid)
        if row is not None:
            _memory_credits[uid] = dict(row)
            return row
    return _normalize_credit_state(_memory_credits.get(uid))


def consume_user_credit(user_id: str, free_allowance: int) -> dict[str, Any]:
    """Consume 1 credit (free trial credits first, then paid Bid Pack credits).

    Returns ``{"consumed": "free"|"paid"|"none", "free_credits_remaining": int,
    "paid_credits": int, "total_credits": int}``.
    """
    uid = str(user_id or "").strip()
    if not uid:
        return {"consumed": "none", "free_credits_remaining": 0, "paid_credits": 0, "total_credits": 0}
    state = get_user_credits(uid)
    consumed = "none"
    if state["free_credits_used"] < free_allowance:
        state["free_credits_used"] += 1
        consumed = "free"
    elif state["paid_credits"] > 0:
        state["paid_credits"] -= 1
        consumed = "paid"

    if consumed != "none":
        _memory_credits[uid] = dict(state)
        if not _use_memory_credits():
            _write_supabase_credits(uid, state)

    free_remaining = max(0, free_allowance - state["free_credits_used"])
    paid = max(0, state["paid_credits"])
    return {
        "consumed": consumed,
        "free_credits_remaining": free_remaining,
        "paid_credits": paid,
        "total_credits": free_remaining + paid,
    }


def grant_user_paid_credits(
    user_id: str,
    credits: int,
    *,
    session_id: str = "",
    stripe_customer_id: str = "",
) -> dict[str, Any]:
    """Idempotently add Bid Pack credits to a user account after checkout."""
    uid = str(user_id or "").strip()
    if not uid or credits <= 0:
        return {"credited": False, "paid_credits": 0}
    state = get_user_credits(uid)
    if session_id and session_id in state["credited_sessions"]:
        return {"credited": False, "reason": "already_credited", "paid_credits": state["paid_credits"]}
    state["paid_credits"] += int(credits)
    if session_id:
        state["credited_sessions"].append(session_id)
    if stripe_customer_id:
        state["stripe_customer_id"] = stripe_customer_id
    _memory_credits[uid] = dict(state)
    persisted = True
    if not _use_memory_credits():
        persisted = _write_supabase_credits(uid, state)
    return {"credited": True, "paid_credits": state["paid_credits"], "persisted": persisted}


def lookup_user_id_by_email(email: str) -> str:
    """Resolve an email address to its ``wa_users.id`` when available."""
    normalized = str(email or "").strip().lower()
    if not normalized:
        return ""
    if os.environ.get("WA_OAUTH_STORE", "").strip().lower() == "memory":
        from procurement_core import oauth

        store = oauth.get_store()
        if hasattr(store, "users"):
            for user in store.users.values():
                if str(user.get("email") or "").strip().lower() == normalized:
                    return str(user.get("id") or "")
        return ""
    if not _supabase_available():
        return ""
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    params = f"email=ilike.{urlencode({'v': escaped})[2:]}&select=id&limit=1"
    try:
        rows = _request("GET", f"wa_users?{params}") or []
    except (HTTPError, URLError, json.JSONDecodeError, RuntimeError):
        return ""
    return str(rows[0].get("id") or "") if rows else ""
