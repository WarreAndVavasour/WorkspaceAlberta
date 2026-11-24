"""Stripe webhook processing: signature verification and provisioning.

Two events close the billing loop (``docs/pricing-and-subscription.md``):

- ``checkout.session.completed`` → :func:`handle_checkout_completed`
  generates a subscriber API key, stores its hash + customer + email in the
  ``wa_subscribers`` Supabase table with ``status='active'``, and (when
  ``STRIPE_SECRET_KEY`` is set) writes the key hash and the plaintext key to
  the Stripe customer's metadata so the owner can copy it from the Stripe
  dashboard into the welcome email. The plaintext key is also kept in the
  row's ``pending_key`` column until first use so manual onboarding works
  without dashboard access.
- ``customer.subscription.deleted`` → :func:`handle_subscription_deleted`
  flips the subscriber row to ``status='cancelled'``. The auth cache TTL
  (5 min) bounds how long a cancelled key keeps working.

Signature verification (:func:`verify_stripe_signature`) implements Stripe's
scheme with stdlib only: the ``Stripe-Signature`` header carries
``t=<timestamp>,v1=<hmac>``; the HMAC-SHA256 of ``"{t}.{raw_body}"`` under
``STRIPE_WEBHOOK_SECRET`` must match a ``v1`` value and the timestamp must be
within ``SIGNATURE_TOLERANCE_SECONDS``.

Everything here is framework-free so it unit-tests without FastAPI; the
route in ``server_http.py`` is a thin shell.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from procurement_core import storage
from procurement_core.auth import (
    SUBSCRIBE_URL,
    clear_cache,
    generate_api_key,
    hash_api_key,
    prefilled_subscribe_url,
    stripe_secret_key,
    supabase_config,
)

SIGNATURE_TOLERANCE_SECONDS = 300
DEFAULT_PRO_PRICE_ID = "price_1TqDAVIOLkCszIIOQIb7YgT3"

PLANS: dict[str, dict[str, Any]] = {
    "pro": {
        "mode": "subscription",
        "name": "WorkspaceAlberta Pro (Unlimited Monthly)",
        "description": "Unlimited tender Requirements Boards, E2B Bid Rooms, Cohere Command A+ reviews, and unlimited watchlist.",
        "unit_amount_cad_cents": 8500,
        "credits": 0,
        "price_env": "WA_STRIPE_PRICE_PRO",
        "default_price_id": DEFAULT_PRO_PRICE_ID,
        "link_env": "WA_STRIPE_LINK_PRO",
        "default_link": SUBSCRIBE_URL,
    },
    "pack_1": {
        "mode": "payment",
        "name": "WorkspaceAlberta Bid Pack — 1 Tender Credit",
        "description": "1 tender credit for classify_tender (Requirements Board), process_bid_room, or analyze_contract_with_cohere. Never expires.",
        "unit_amount_cad_cents": 1900,
        "credits": 1,
        "price_env": "WA_STRIPE_PRICE_PACK_1",
        "default_price_id": "",
        "link_env": "WA_STRIPE_LINK_PACK_1",
        "default_link": "",
    },
    "pack_3": {
        "mode": "payment",
        "name": "WorkspaceAlberta Bid Pack — 3 Tender Credits",
        "description": "3 tender credits for classify_tender (Requirements Board), process_bid_room, or analyze_contract_with_cohere. Never expires.",
        "unit_amount_cad_cents": 4900,
        "credits": 3,
        "price_env": "WA_STRIPE_PRICE_PACK_3",
        "default_price_id": "",
        "link_env": "WA_STRIPE_LINK_PACK_3",
        "default_link": "",
    },
}


class WebhookError(Exception):
    """Webhook failure with an HTTP status for the route to return."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


# ============== Signature verification ==============


def verify_stripe_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str | None = None,
    tolerance: int = SIGNATURE_TOLERANCE_SECONDS,
) -> None:
    """Raise :class:`WebhookError` (400) unless the signature is valid."""
    secret = secret if secret is not None else os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise WebhookError(503, "STRIPE_WEBHOOK_SECRET is not configured.")
    if not signature_header:
        raise WebhookError(400, "Missing Stripe-Signature header.")

    timestamp = ""
    candidates: list[str] = []
    for part in signature_header.split(","):
        name, _, value = part.strip().partition("=")
        if name == "t":
            timestamp = value
        elif name == "v1":
            candidates.append(value)

    if not timestamp or not candidates:
        raise WebhookError(400, "Malformed Stripe-Signature header.")
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            raise WebhookError(400, "Stripe signature timestamp outside tolerance.")
    except ValueError as exc:
        raise WebhookError(400, "Invalid Stripe signature timestamp.") from exc

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise WebhookError(400, "Stripe signature verification failed.")


# ============== Upstream helpers ==============


def _supabase_request(method: str, path_query: str, payload: Any = None, prefer: str = "return=minimal") -> Any:
    url, service_key = supabase_config()
    if not (url and service_key):
        raise WebhookError(503, "Supabase is not configured for provisioning.")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{url}/rest/v1/{path_query}",
        data=data,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": prefer,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise WebhookError(502, f"Supabase {method} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise WebhookError(502, f"Supabase unreachable: {exc.reason}") from exc
    return json.loads(body) if body else None


def _stripe_post(path: str, fields: dict[str, str]) -> dict[str, Any]:
    """POST form-encoded fields to Stripe API and return parsed JSON."""
    secret = stripe_secret_key()
    if not secret:
        raise WebhookError(503, "STRIPE_SECRET_KEY is not configured.")
    request = Request(
        f"https://api.stripe.com/v1/{path.lstrip('/')}",
        data=urlencode(fields).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise WebhookError(502, f"Stripe {path} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise WebhookError(502, f"Stripe unreachable: {exc.reason}") from exc
    return json.loads(body) if body else {}


def _stripe_set_customer_metadata(customer_id: str, metadata: dict[str, str]) -> bool:
    """Best-effort metadata write; returns False when no key configured."""
    if not stripe_secret_key():
        return False
    fields = {f"metadata[{k}]": v for k, v in metadata.items()}
    try:
        _stripe_post(f"customers/{customer_id}", fields)
    except WebhookError:
        return False
    return True


def create_checkout_session(
    plan: str = "pro",
    *,
    email: str = "",
    user_id: str = "",
    origin: str = "",
) -> dict[str, Any]:
    """Create a Stripe Checkout Session (or prefilled Payment Link fallback).

    Binds ``client_reference_id`` (``user_id``) and ``customer_email`` so
    paying from a different accounting/work email still unlocks the exact
    signed-in MCP account.
    """
    plan_key = str(plan or "pro").strip().lower()
    spec = PLANS.get(plan_key)
    if not spec:
        raise WebhookError(400, f"Unknown plan '{plan}'. Valid plans: {', '.join(PLANS)}.")

    clean_email = str(email or "").strip().lower()
    clean_user_id = str(user_id or "").strip()
    base_origin = (
        str(origin or "").strip().rstrip("/")
        or os.environ.get("WA_PUBLIC_ORIGIN", "").strip().rstrip("/")
        or "https://elbowsupknivesout.warreandvavasour.com"
    )

    secret = stripe_secret_key()
    price_id = os.environ.get(spec["price_env"], "").strip() or spec["default_price_id"]
    fallback_link = os.environ.get(spec["link_env"], "").strip() or spec["default_link"]

    if secret:
        fields: dict[str, str] = {
            "mode": spec["mode"],
            "allow_promotion_codes": "true",
            "success_url": f"{base_origin}/billing/success?plan={plan_key}&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{base_origin}/pricing",
            "line_items[0][quantity]": "1",
            "metadata[wa_plan]": plan_key,
            "metadata[wa_credits]": str(spec["credits"]),
        }
        if price_id:
            fields["line_items[0][price]"] = price_id
        else:
            fields["line_items[0][price_data][currency]"] = "cad"
            fields["line_items[0][price_data][unit_amount]"] = str(spec["unit_amount_cad_cents"])
            fields["line_items[0][price_data][product_data][name]"] = spec["name"]
            fields["line_items[0][price_data][product_data][description]"] = spec["description"]
            if spec["mode"] == "subscription":
                fields["line_items[0][price_data][recurring][interval]"] = "month"
        if clean_user_id:
            fields["client_reference_id"] = clean_user_id
            fields["metadata[wa_user_id]"] = clean_user_id
        if clean_email:
            fields["customer_email"] = clean_email
        if spec["mode"] == "payment":
            fields["customer_creation"] = "if_required"
        session = _stripe_post("checkout/sessions", fields)
        url = str(session.get("url") or "").strip()
        if not url:
            raise WebhookError(502, "Stripe Checkout session returned no URL.")
        return {"url": url, "session_id": session.get("id", ""), "plan": plan_key, "source": "stripe_session"}

    if fallback_link:
        url = prefilled_subscribe_url(email=clean_email, user_id=clean_user_id, base_url=fallback_link)
        return {"url": url, "session_id": "", "plan": plan_key, "source": "payment_link"}

    raise WebhookError(
        503,
        f"Checkout for '{plan_key}' is not configured yet (set STRIPE_SECRET_KEY or {spec['link_env']}).",
    )


def create_billing_portal_session(customer_id: str = "", *, return_url: str = "") -> dict[str, Any]:
    """Create a self-serve Stripe Billing Portal session for managing or cancelling Pro."""
    portal_fallback = os.environ.get("WA_STRIPE_PORTAL_URL", "").strip()
    clean_customer = str(customer_id or "").strip()
    ret = (
        str(return_url or "").strip()
        or (
            os.environ.get("WA_PUBLIC_ORIGIN", "").strip().rstrip("/")
            or "https://elbowsupknivesout.warreandvavasour.com"
        )
        + "/pricing"
    )
    if clean_customer and stripe_secret_key():
        session = _stripe_post(
            "billing_portal/sessions",
            {"customer": clean_customer, "return_url": ret},
        )
        url = str(session.get("url") or "").strip()
        if url:
            return {"url": url, "source": "stripe_portal"}
    if portal_fallback:
        return {"url": portal_fallback, "source": "static_portal"}
    raise WebhookError(
        503,
        "Self-serve billing portal requires an active Stripe customer record and STRIPE_SECRET_KEY (or WA_STRIPE_PORTAL_URL).",
    )


# ============== Event handlers ==============


def _write_subscriber_row(method: str, path_query: str, payload: Any) -> Any:
    """Write wa_subscribers, gracefully omitting user_id if migration 005 is not yet applied."""
    try:
        return _supabase_request(method, path_query, payload)
    except WebhookError as exc:
        if exc.status_code != 502 or "user_id" not in str(exc):
            raise
        if isinstance(payload, list):
            stripped = [{k: v for k, v in row.items() if k != "user_id"} for row in payload]
        elif isinstance(payload, dict):
            stripped = {k: v for k, v in payload.items() if k != "user_id"}
        else:
            raise
        return _supabase_request(method, path_query, stripped)


def handle_checkout_completed(event_object: dict[str, Any]) -> dict[str, Any]:
    """Provision a Pro subscription OR Bid Pack credits from a completed checkout."""
    customer_id = str(event_object.get("customer") or "").strip()
    email = str(
        (event_object.get("customer_details") or {}).get("email")
        or event_object.get("customer_email")
        or ""
    ).strip()
    metadata = event_object.get("metadata") if isinstance(event_object.get("metadata"), dict) else {}
    client_ref = str(event_object.get("client_reference_id") or metadata.get("wa_user_id") or "").strip()
    mode = str(event_object.get("mode") or "").strip().lower()
    wa_plan = str(metadata.get("wa_plan") or "").strip().lower()
    session_id = str(event_object.get("id") or "").strip()

    # One-time Bid Pack checkout -> add non-expiring paid tender credits.
    try:
        credits_meta = int(metadata.get("wa_credits") or 0)
    except (TypeError, ValueError):
        credits_meta = 0
    if mode == "payment" or wa_plan in {"pack_1", "pack_3"} or credits_meta > 0:
        credits_to_add = credits_meta or int((PLANS.get(wa_plan) or {}).get("credits") or 1)
        user_id = client_ref or storage.lookup_user_id_by_email(email)
        if not user_id:
            raise WebhookError(
                400,
                "Bid Pack checkout completed without a linked user_id or matching signed-in email.",
            )
        grant = storage.grant_user_paid_credits(
            user_id,
            credits_to_add,
            session_id=session_id,
            stripe_customer_id=customer_id,
        )
        return {
            "provisioned": bool(grant.get("credited")),
            "kind": "bid_pack",
            "plan": wa_plan or f"pack_{credits_to_add}",
            "credits_added": credits_to_add if grant.get("credited") else 0,
            "paid_credits": grant.get("paid_credits", 0),
            "user_id": user_id,
            "customer": customer_id,
            "email": email,
        }

    if not customer_id:
        raise WebhookError(400, "checkout.session.completed without a customer id.")

    # Idempotency: an existing active row for this customer keeps its key
    # (but still backfills user_id when newly provided).
    params = urlencode({"stripe_customer_id": f"eq.{customer_id}", "select": "key_hash,status", "limit": "1"})
    existing = _supabase_request("GET", f"wa_subscribers?{params}") or []
    if existing and existing[0].get("status") == "active":
        if client_ref:
            _write_subscriber_row("PATCH", f"wa_subscribers?{urlencode({'stripe_customer_id': f'eq.{customer_id}'})}", {"user_id": client_ref})
        return {"provisioned": False, "reason": "already active", "customer": customer_id}

    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    row: dict[str, Any] = {
        "key_hash": key_hash,
        "stripe_customer_id": customer_id,
        "email": email,
        "status": "active",
        "plan": "pro",
        "pending_key": api_key,
    }
    if client_ref:
        row["user_id"] = client_ref
    if existing:
        params = urlencode({"stripe_customer_id": f"eq.{customer_id}"})
        _write_subscriber_row("PATCH", f"wa_subscribers?{params}", row)
    else:
        _write_subscriber_row("POST", "wa_subscribers", [row])

    metadata_written = _stripe_set_customer_metadata(
        customer_id, {"wa_key_hash": key_hash, "wa_api_key": api_key}
    )
    clear_cache()
    return {
        "provisioned": True,
        "customer": customer_id,
        "email": email,
        "user_id": client_ref,
        "key_in_stripe_metadata": metadata_written,
    }


def handle_subscription_deleted(event_object: dict[str, Any]) -> dict[str, Any]:
    """Revoke access when a subscription is cancelled."""
    customer_id = str(event_object.get("customer") or "").strip()
    if not customer_id:
        raise WebhookError(400, "customer.subscription.deleted without a customer id.")
    params = urlencode({"stripe_customer_id": f"eq.{customer_id}"})
    _supabase_request("PATCH", f"wa_subscribers?{params}", {"status": "cancelled"})
    clear_cache()
    return {"revoked": True, "customer": customer_id}


def process_webhook_event(payload: bytes, signature_header: str | None) -> dict[str, Any]:
    """Verify and dispatch one webhook delivery. Returns a summary dict."""
    verify_stripe_signature(payload, signature_header)
    try:
        event = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WebhookError(400, "Webhook payload is not valid JSON.") from exc

    event_type = event.get("type", "")
    event_object = (event.get("data") or {}).get("object") or {}
    if event_type == "checkout.session.completed":
        result = handle_checkout_completed(event_object)
    elif event_type == "customer.subscription.deleted":
        result = handle_subscription_deleted(event_object)
    else:
        result = {"ignored": True}
    result["event_type"] = event_type
    return result
