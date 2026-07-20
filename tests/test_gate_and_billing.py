"""Tests for the Pro-tool gate, auth module, and Stripe webhook processing.

No live network calls: Supabase/Stripe lookups are monkeypatched, and
webhook signatures are generated locally with the same HMAC scheme Stripe
uses.
"""

import hashlib
import hmac
import json
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")

from procurement_core import auth, billing, storage  # noqa: E402


def make_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


class KeyMaterialTest(unittest.TestCase):
    def test_generate_and_hash(self):
        key = auth.generate_api_key()
        self.assertTrue(key.startswith(auth.KEY_PREFIX))
        self.assertEqual(len(auth.hash_api_key(key)), 64)
        self.assertEqual(auth.hash_api_key(key), auth.hash_api_key(f"  {key}  "))

    def test_extract_bearer(self):
        self.assertEqual(auth.extract_bearer_key("Bearer abc"), "abc")
        self.assertEqual(auth.extract_bearer_key("bearer abc"), "abc")
        self.assertEqual(auth.extract_bearer_key("Basic abc"), "")
        self.assertEqual(auth.extract_bearer_key(None), "")


class GateTest(unittest.TestCase):
    def setUp(self):
        auth.clear_cache()

    def tearDown(self):
        auth.clear_cache()

    def test_gate_disabled_without_config(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(auth.gate_enabled())
            self.assertIsNone(auth.check_tool_access("process_bid_room", None))

    def test_gate_disabled_flag_wins(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k", "WA_GATE_DISABLED": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(auth.gate_enabled())

    def test_pro_tool_requires_key(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(auth.GateError) as ctx:
                auth.check_tool_access("process_bid_room", None)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_free_tool_anonymous_ok(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIsNone(auth.check_tool_access("search_opportunities", None))

    def test_active_subscriber_passes(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        key = auth.generate_api_key()
        record = {"key_hash": auth.hash_api_key(key), "status": "active", "plan": "pro"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(auth, "_supabase_lookup", return_value=record):
                result = auth.check_tool_access("process_bid_room", f"Bearer {key}")
        self.assertEqual(result["status"], "active")

    def test_cancelled_subscriber_402(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        key = auth.generate_api_key()
        record = {"key_hash": auth.hash_api_key(key), "status": "cancelled"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(auth, "_supabase_lookup", return_value=record):
                with self.assertRaises(auth.GateError) as ctx:
                    auth.check_tool_access("process_bid_room", f"Bearer {key}")
        self.assertEqual(ctx.exception.status_code, 402)

    def test_unknown_key_401_and_cached(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        key = auth.generate_api_key()
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(auth, "_supabase_lookup", return_value=None) as lookup:
                for _ in range(3):
                    with self.assertRaises(auth.GateError) as ctx:
                        auth.check_tool_access("watch_opportunity", f"Bearer {key}")
                    self.assertEqual(ctx.exception.status_code, 401)
                self.assertEqual(lookup.call_count, 1)  # TTL cache

    def test_bad_key_on_free_tool_degrades_to_anonymous(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(auth, "_supabase_lookup", return_value=None):
                result = auth.check_tool_access("search_opportunities", "Bearer wa_live_bogus")
        self.assertIsNone(result)


class WebhookSignatureTest(unittest.TestCase):
    SECRET = "whsec_testsecret"

    def test_valid_signature(self):
        payload = json.dumps({"type": "ping"}).encode()
        header = make_signature(payload, self.SECRET)
        billing.verify_stripe_signature(payload, header, secret=self.SECRET)

    def test_wrong_secret_rejected(self):
        payload = b"{}"
        header = make_signature(payload, "whsec_other")
        with self.assertRaises(billing.WebhookError) as ctx:
            billing.verify_stripe_signature(payload, header, secret=self.SECRET)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_old_timestamp_rejected(self):
        payload = b"{}"
        header = make_signature(payload, self.SECRET, timestamp=int(time.time()) - 4000)
        with self.assertRaises(billing.WebhookError):
            billing.verify_stripe_signature(payload, header, secret=self.SECRET)

    def test_missing_header_rejected(self):
        with self.assertRaises(billing.WebhookError):
            billing.verify_stripe_signature(b"{}", None, secret=self.SECRET)


class WebhookEventTest(unittest.TestCase):
    SECRET = "whsec_testsecret"

    def _event(self, event_type: str, obj: dict) -> bytes:
        return json.dumps({"type": event_type, "data": {"object": obj}}).encode()

    def test_checkout_completed_provisions(self):
        payload = self._event(
            "checkout.session.completed",
            {"customer": "cus_123", "customer_details": {"email": "owner@shop.ca"}},
        )
        header = make_signature(payload, self.SECRET)
        calls = []

        def fake_supabase(method, path, body=None, prefer="return=minimal"):
            calls.append((method, path, body))
            if method == "GET":
                return []
            return None

        env = {"STRIPE_WEBHOOK_SECRET": self.SECRET}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(billing, "_supabase_request", side_effect=fake_supabase):
                with mock.patch.object(billing, "_stripe_set_customer_metadata", return_value=True):
                    result = billing.process_webhook_event(payload, header)

        self.assertTrue(result["provisioned"])
        self.assertEqual(result["customer"], "cus_123")
        post = next(c for c in calls if c[0] == "POST")
        row = post[2][0]
        self.assertEqual(row["status"], "active")
        self.assertTrue(row["pending_key"].startswith(auth.KEY_PREFIX))
        self.assertEqual(row["key_hash"], auth.hash_api_key(row["pending_key"]))

    def test_checkout_idempotent_when_active(self):
        payload = self._event("checkout.session.completed", {"customer": "cus_123"})
        header = make_signature(payload, self.SECRET)

        def fake_supabase(method, path, body=None, prefer="return=minimal"):
            if method == "GET":
                return [{"key_hash": "abc", "status": "active"}]
            raise AssertionError("should not write")

        with mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": self.SECRET}, clear=True):
            with mock.patch.object(billing, "_supabase_request", side_effect=fake_supabase):
                result = billing.process_webhook_event(payload, header)
        self.assertFalse(result["provisioned"])

    def test_subscription_deleted_revokes(self):
        payload = self._event("customer.subscription.deleted", {"customer": "cus_123"})
        header = make_signature(payload, self.SECRET)
        calls = []

        def fake_supabase(method, path, body=None, prefer="return=minimal"):
            calls.append((method, path, body))
            return None

        with mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": self.SECRET}, clear=True):
            with mock.patch.object(billing, "_supabase_request", side_effect=fake_supabase):
                result = billing.process_webhook_event(payload, header)
        self.assertTrue(result["revoked"])
        self.assertEqual(calls[0][0], "PATCH")
        self.assertEqual(calls[0][2], {"status": "cancelled"})

    def test_unknown_event_ignored(self):
        payload = self._event("invoice.paid", {})
        header = make_signature(payload, self.SECRET)
        with mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": self.SECRET}, clear=True):
            result = billing.process_webhook_event(payload, header)
        self.assertTrue(result["ignored"])


class TenantStorageTest(unittest.TestCase):
    def test_anonymous_uses_local_files(self):
        self.assertIsNone(storage.current_tenant())
        self.assertFalse(storage.tenant_active())

    def test_tenant_context_set_reset(self):
        token = storage.set_tenant("hash123")
        self.assertEqual(storage.current_tenant(), "hash123")
        storage.reset_tenant(token)
        self.assertIsNone(storage.current_tenant())

    def test_tenant_profile_routed_to_supabase(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        from procurement_core import service

        token = storage.set_tenant("hash123")
        try:
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(storage, "_request", return_value=[{"profile": {"company_name": "T"}}]):
                    profile = service.load_profile()
        finally:
            storage.reset_tenant(token)
        self.assertEqual(profile, {"company_name": "T"})


class HttpGateIntegrationTest(unittest.TestCase):
    """End-to-end REST gate via the FastAPI test client."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("fastapi testclient unavailable")
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        import server_http

        cls.client = TestClient(server_http.app)

    def setUp(self):
        auth.clear_cache()

    def test_health_reports_gate(self):
        body = self.client.get("/health").json()
        self.assertIn("gate", body)
        self.assertIn("process_bid_room", body["gate"]["pro_tools"])

    def test_pro_tool_blocked_without_key(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            response = self.client.post("/tools/list_watchlist", json={})
        self.assertEqual(response.status_code, 401)

    def test_pro_tool_allowed_with_valid_key(self):
        env = {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "CANADABUYS_LOAD_ENV_FILE": "0",
        }
        key = auth.generate_api_key()
        record = {"key_hash": auth.hash_api_key(key), "status": "active", "plan": "pro"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(auth, "_supabase_lookup", return_value=record):
                with mock.patch.object(storage, "_request", return_value=[{"watchlist": []}]):
                    response = self.client.post(
                        "/tools/list_watchlist",
                        json={},
                        headers={"Authorization": f"Bearer {key}"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertIn("empty", response.json()["content"].lower())

    def test_free_tool_open_when_gated(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            response = self.client.post("/tools/summarize_contracts", json={})
        self.assertEqual(response.status_code, 200)

    def test_me_requires_key(self):
        self.assertEqual(self.client.get("/me").status_code, 401)

    def test_webhook_rejects_unsigned(self):
        with mock.patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_x"}, clear=True):
            response = self.client.post("/stripe/webhook", content=b"{}")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
