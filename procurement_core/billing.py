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

from procurement_core.auth import (
    clear_cache,
    generate_api_key,
    hash_api_key,
    stripe_secret_key,
    supabase_config,
)

SIGNATURE_TOLERANCE_SECONDS = 300


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


def _stripe_set_customer_metadata(customer_id: str, metadata: dict[str, str]) -> bool:
    """Best-effort metadata write; returns False when no key configured."""
    secret = stripe_secret_key()
    if not secret:
        return False
    fields = {f"metadata[{k}]": v for k, v in metadata.items()}
    request = Request(
        f"https://api.stripe.com/v1/customers/{customer_id}",
        data=urlencode(fields).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            response.read()
    except (HTTPError, URLError):
        return False
    return True


# ============== Event handlers ==============


def handle_checkout_completed(event_object: dict[str, Any]) -> dict[str, Any]:
    """Provision a subscriber from a completed checkout session."""
    customer_id = str(event_object.get("customer") or "").strip()
    email = str((event_object.get("customer_details") or {}).get("email") or event_object.get("customer_email") or "").strip()
    if not customer_id:
        raise WebhookError(400, "checkout.session.completed without a customer id.")

    # Idempotency: an existing active row for this customer keeps its key.
    params = urlencode({"stripe_customer_id": f"eq.{customer_id}", "select": "key_hash,status", "limit": "1"})
    existing = _supabase_request("GET", f"wa_subscribers?{params}") or []
    if existing and existing[0].get("status") == "active":
        return {"provisioned": False, "reason": "already active", "customer": customer_id}

    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    row = {
        "key_hash": key_hash,
        "stripe_customer_id": customer_id,
        "email": email,
        "status": "active",
        "plan": "pro",
        "pending_key": api_key,
    }
    if existing:
        params = urlencode({"stripe_customer_id": f"eq.{customer_id}"})
        _supabase_request("PATCH", f"wa_subscribers?{params}", row)
    else:
        _supabase_request("POST", "wa_subscribers", [row])

    metadata_written = _stripe_set_customer_metadata(
        customer_id, {"wa_key_hash": key_hash, "wa_api_key": api_key}
    )
    clear_cache()
    return {
        "provisioned": True,
        "customer": customer_id,
        "email": email,
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
