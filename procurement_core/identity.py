"""Unified Bearer identity for API keys and OAuth access tokens.

``check_tool_access`` is the single gate used by REST and the hosted MCP
adapter. A valid ``wa_live_`` key or a workspaceAlberta OAuth access token
both become a tenant record. Pro tools additionally require an active
``wa_subscribers`` row (matched by key hash or by email).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from procurement_core import auth, oauth, storage
from procurement_core.auth import GateError

_subscriber_lookup = None


def set_subscriber_lookup(lookup) -> None:
    """Tests inject a subscriber-by-email function. Pass None to restore."""
    global _subscriber_lookup
    _subscriber_lookup = lookup


def _api_key_record(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    enriched.setdefault("auth_type", "api_key")
    enriched.setdefault("tenant_id", record.get("key_hash"))
    enriched.setdefault("pro_active", record.get("status") == "active")
    return enriched


def lookup_subscriber_by_email(email: str) -> dict[str, Any] | None:
    """Return the newest matching subscriber row for a normalized email."""
    email = oauth.normalize_email(email)
    if not email:
        return None
    if _subscriber_lookup is not None:
        return _subscriber_lookup(email)
    url, service_key = auth.supabase_config()
    if not (url and service_key):
        return None
    # ilike + escaped wildcards: existing Stripe rows may not be lowercase.
    escaped = email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    params = (
        f"email=ilike.{quote(escaped)}"
        f"&select=key_hash,stripe_customer_id,email,status,plan"
        f"&order=updated_at.desc"
        f"&limit=1"
    )
    request_url = f"{url}/rest/v1/wa_subscribers?{params}"
    request = Request(
        request_url,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        return None
    return rows[0] if rows else None


def identity_from_oauth_claims(claims: dict[str, Any]) -> dict[str, Any]:
    email = oauth.normalize_email(str(claims.get("email") or ""))
    user_id = str(claims.get("sub") or "")
    subscriber = lookup_subscriber_by_email(email) if email else None
    pro_active = bool(subscriber and subscriber.get("status") == "active")
    return {
        "auth_type": "oauth",
        "tenant_id": f"user:{user_id}" if user_id else None,
        "user_id": user_id,
        "email": email,
        "key_hash": (subscriber or {}).get("key_hash"),
        "stripe_customer_id": (subscriber or {}).get("stripe_customer_id", ""),
        "status": (subscriber or {}).get("status") or "none",
        "plan": (subscriber or {}).get("plan") or "free",
        "pro_active": pro_active,
    }


def resolve_bearer(authorization_header: str | None) -> dict[str, Any] | None:
    """Return a tenant record or raise :class:`GateError` for a bad token.

    Missing headers return None (anonymous). Unknown token types are 401.
    """
    key = auth.extract_bearer_key(authorization_header)
    if not key:
        return None
    if key.startswith(auth.KEY_PREFIX):
        return _api_key_record(auth.validate_key(key))
    if key.startswith(oauth.ACCESS_PREFIX):
        claims = oauth.validate_access_token(key)
        return identity_from_oauth_claims(claims)
    raise GateError(401, "Unrecognized Bearer token.")


def has_presentable_identity(authorization_header: str | None) -> bool:
    """True when the caller is signed in, even if their Pro plan is inactive.

    Used by the MCP HTTP gate: a cancelled subscriber must not get a 401
    (that would restart OAuth). They fall through to the existing 402 copy.
    """
    try:
        key = auth.extract_bearer_key(authorization_header)
        if key and key.startswith(oauth.ACCESS_PREFIX):
            # The HTTP challenge only needs identity. Subscription lookup
            # happens once in the tool gate, rather than twice per OAuth call.
            oauth.validate_access_token(key)
            return True
        record = resolve_bearer(authorization_header)
    except GateError as exc:
        return exc.status_code != 401
    return record is not None


def tenant_id_for(record: dict[str, Any] | None) -> str | None:
    if not record:
        return None
    return record.get("tenant_id") or record.get("key_hash")


def check_tool_access(tool_name: str, authorization_header: str | None) -> dict[str, Any] | None:
    """Gate one tool call. Returns the identity record when authenticated.

    Rules (same as ``auth.check_tool_access``, plus OAuth tokens):

    - Gate disabled: honour a valid identity when present so profiles stay
      per-user, otherwise anonymous.
    - A valid key or access token is honoured on any tool.
    - Hosted saved-profile tools and Pro tools without an identity raise 401.
    - Saved-profile tools require sign-in, but no paid subscription.
    - Pro tools with a signed-in user who has no active subscription raise 402.
    - Free tools with a bad token degrade to anonymous.
    """
    is_pro = tool_name in auth.PRO_TOOLS
    requires_identity = is_pro or tool_name in auth.SIGN_IN_TOOLS
    key = auth.extract_bearer_key(authorization_header)

    if not auth.gate_enabled() and not storage.is_hosted():
        if not key:
            return None
        try:
            return resolve_bearer(authorization_header)
        except GateError:
            return None

    if not key:
        if requires_identity:
            raise GateError(401, "Sign in to workspaceAlberta to use this tool. Signing in does not charge you.")
        return None

    try:
        record = resolve_bearer(authorization_header)
    except GateError:
        if requires_identity:
            raise
        return None

    if is_pro and not record.get("pro_active"):
        raise GateError(
            402,
            "Your workspaceAlberta Pro subscription is not active. "
            "Subscribe at https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a.",
        )
    return record
