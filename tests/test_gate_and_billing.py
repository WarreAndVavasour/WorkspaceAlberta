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
os.environ.setdefault("WA_OAUTH_STORE", "memory")
os.environ.setdefault("WA_OAUTH_SIGNING_KEY", "test-oauth-signing-key")

from procurement_core import auth, billing, storage  # noqa: E402


def make_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    signed = f"{ts}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


class AccessHelpTest(unittest.TestCase):
    def test_help_names_checkout_steps_and_no_third_party_keys(self):
        from procurement_core.auth import access_help, access_help_text

        pro = access_help(401, "classify_tender")
        self.assertEqual(pro["requires"], "pro")
        self.assertIn("buy.stripe.com", pro["steps"][-1])
        free = access_help(401, "set_business_profile")
        self.assertEqual(free["requires"], "sign_in")
        self.assertIn("never starts a paid subscription", free["steps"][-1])
        lapsed = access_help_text(402, "list_watchlist")
        self.assertTrue(lapsed.startswith("1. Subscribe"))
        self.assertIn("Do not paste API keys", lapsed)


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
                        auth.check_tool_access("classify_tender", f"Bearer {key}")
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
        self.assertIn("classify_tender", body["gate"]["pro_tools"])

    def test_pro_tool_blocked_without_key(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            response = self.client.post("/tools/list_watchlist", json={})
        self.assertEqual(response.status_code, 401)
        self.assertIn("resource_metadata=", response.headers.get("www-authenticate", ""))

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

    def test_checkout_redirects_to_prefilled_payment_link_without_stripe_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            res = self.client.get(
                "/checkout?plan=pro&email=Owner@Shop.ca&user_id=user-123",
                follow_redirects=False,
            )
        self.assertEqual(res.status_code, 303)
        location = res.headers["location"]
        self.assertIn("buy.stripe.com", location)
        self.assertIn("prefilled_email=owner%40shop.ca", location)
        self.assertIn("client_reference_id=user-123", location)

    def test_checkout_creates_dynamic_bid_pack_session_with_stripe_key(self):
        captured = {}

        def fake_stripe_post(path, fields):
            captured["path"] = path
            captured["fields"] = fields
            return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}

        with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123"}, clear=True):
            with mock.patch.object(billing, "_stripe_post", side_effect=fake_stripe_post):
                res = self.client.get(
                    "/checkout?plan=pack_3&email=estimator@shop.ca&user_id=uid-9",
                    follow_redirects=False,
                )
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "https://checkout.stripe.com/c/pay/cs_test_1")
        self.assertEqual(captured["path"], "checkout/sessions")
        self.assertEqual(captured["fields"]["mode"], "payment")
        self.assertEqual(captured["fields"]["client_reference_id"], "uid-9")
        self.assertEqual(captured["fields"]["customer_email"], "estimator@shop.ca")
        self.assertEqual(captured["fields"]["metadata[wa_credits]"], "3")
        self.assertEqual(captured["fields"]["line_items[0][price_data][unit_amount]"], "4900")

    def test_billing_success_and_portal_pages(self):
        ok_pro = self.client.get("/billing/success?plan=pro")
        self.assertEqual(ok_pro.status_code, 200)
        self.assertIn("Pro is active", ok_pro.text)
        ok_pack = self.client.get("/billing/success?plan=pack_3")
        self.assertEqual(ok_pack.status_code, 200)
        self.assertIn("3 non-expiring tender credits", ok_pack.text)
        portal_page = self.client.get("/billing/portal")
        self.assertEqual(portal_page.status_code, 200)
        self.assertIn("Stripe Billing Portal", portal_page.text)

    def test_billing_portal_post_redirects_with_stripe_session(self):
        from procurement_core import identity

        with mock.patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_123"}, clear=True):
            with mock.patch.object(
                identity, "lookup_subscriber_by_email", return_value={"stripe_customer_id": "cus_99"}
            ):
                with mock.patch.object(
                    billing, "_stripe_post", return_value={"url": "https://billing.stripe.com/session/live_1"}
                ):
                    res = self.client.post(
                        "/billing/portal",
                        data={"email": "owner@shop.ca"},
                        follow_redirects=False,
                    )
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "https://billing.stripe.com/session/live_1")

    def test_features_page_serves_new_tools_and_nav_link(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn('href="/features"', home.text)
        features = self.client.get("/features")
        self.assertEqual(features.status_code, 200)
        for expected in (
            "get_buyer_award_history",
            "classify_tender",
            "process_bid_room",
            "bid_no_bid_scorecard",
            "2 free",
            "/pricing",
        ):
            self.assertIn(expected, features.text)

    def test_awards_history_route_is_pro_gated(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True):
            res = self.client.post("/awards/history", json={"buyer": "PSPC"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("resource_metadata=", res.headers.get("www-authenticate", ""))


class AwardsIntelligenceTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from procurement_core import service

        self._tmp = tempfile.TemporaryDirectory()
        self._old_data_dir = service.DATA_DIR
        service.DATA_DIR = Path(self._tmp.name)
        self.fixture_csv = Path(self._tmp.name) / "awards.csv"
        self.fixture_csv.write_text(
            "title-titre-eng,referenceNumber-numeroReference,solicitationNumber-numeroSollicitation,"
            "contractAwardDate-dateAttributionContrat,contractAmount-montantContrat,totalContractValue-valeurTotaleContrat,"
            "contractCurrency-contratMonnaie,supplierLegalName-nomLegalFournisseur-eng,supplierAddressCity-fournisseurAdresseVille-eng,"
            "supplierAddressProvince-fournisseurAdresseProvince-eng,contractingEntityName-nomEntitContractante-eng,"
            "endUserEntitiesName-nomEntitesUtilisateurFinal-eng,unspsc,unspscDescription-eng,gsin-nibs,"
            "gsinDescription-nibsDescription-eng,regionsOfDelivery-regionsLivraison-eng,procurementMethod-methodeApprovisionnement-eng,"
            "awardDescription-descriptionAttribution-eng\n"
            "Structural Steel Bridge Repair,PW-26-001,SOL-1,2026-06-15,420000.00,0,CAD,Prairie Ironworks Ltd.,Red Deer,Alberta,"
            "Public Services and Procurement Canada,Transport Canada,72151900,Structural steel work,5139,Steel,Alberta,Open bidding,Bridge girders\n"
            "Structural Steel Overpass Fabrication,PW-26-002,SOL-2,2026-08-20,280000.00,0,CAD,Prairie Ironworks Ltd.,Red Deer,Alberta,"
            "Public Services and Procurement Canada,Transport Canada,72151900,Structural steel work,5139,Steel,Alberta,Open bidding,Steel fabrication\n"
            "Structural Steel Guardrails,PW-26-003,SOL-3,2026-09-10,600000.00,0,CAD,Northern Fabricators Inc.,Edmonton,Alberta,"
            "Public Services and Procurement Canada,Transport Canada,72151900,Structural steel work,5139,Steel,Alberta,Open bidding,Guardrails\n",
            encoding="utf-8",
        )

    def tearDown(self):
        from procurement_core import service

        service.DATA_DIR = self._old_data_dir
        self._tmp.cleanup()

    def test_fiscal_years_roll_over_in_april(self):
        from datetime import datetime, timezone
        from procurement_core import awards

        self.assertEqual(awards.current_fiscal_years(datetime(2026, 11, 24, tzinfo=timezone.utc)), ["2026-2027", "2025-2026"])
        self.assertEqual(awards.current_fiscal_years(datetime(2026, 2, 15, tzinfo=timezone.utc)), ["2025-2026", "2024-2025"])

    def test_canadabuys_sqlite_ingest_query_incumbent_and_structured_tool(self):
        import asyncio
        from procurement_core import awards, service

        with mock.patch.dict(os.environ, {"PROCUREMENT_FIXTURE_DIR": str(self.fixture_csv.parent)}, clear=False):
            text, structured = asyncio.run(
                service.call_tool_text_and_structured(
                    "get_buyer_award_history",
                    {"buyer": "Public Services", "keywords": "steel", "source": "federal", "limit": 10},
                )
            )
        self.assertEqual(structured["kind"], "award_history")
        self.assertEqual(structured["count"], 3)
        self.assertEqual(structured["summary"]["min_cad"], 280000.0)
        self.assertEqual(structured["summary"]["median_cad"], 420000.0)
        self.assertEqual(structured["summary"]["max_cad"], 600000.0)
        self.assertEqual(structured["summary"]["incumbents"][0]["supplier"], "Prairie Ironworks Ltd.")
        self.assertEqual(structured["summary"]["incumbents"][0]["wins"], 2)
        self.assertIn("Prairie Ironworks Ltd.", text)
        self.assertIn("Potential incumbent(s)", text)

        # Quick teaser for free scorecard reads from the local awards.db with zero network calls.
        teaser = awards.quick_cached_award_teaser(
            {"buyer": "Public Services and Procurement Canada", "title": "Structural Steel Truss", "unspsc": "72151900"}
        )
        self.assertIn("3 comparable historical award(s)", teaser)
        self.assertIn("repeat winner detected", teaser)

    def test_apc_award_extraction_includes_winner_value_and_competition_count(self):
        from procurement_core import awards

        detail = {
            "opportunity": {
                "referenceNumber": "AB-2026-07074",
                "shortTitle": "FIREWOOD STORAGE SHED REPLACEMENT",
                "contractingOrganizationName": "Alberta Forestry and Parks",
                "actualValue": 35643.58,
                "awardedOnUtc": "2026-11-13T20:33:33Z",
            },
            "awards": [
                {
                    "alternativeSupplierDisplayName": "Powerband Projects Inc.",
                    "awardDate": "2026-11-09T00:00:00",
                    "amount": 35643.58,
                    "address": {"city": "Red Deer", "stateProvince": "CA-AB"},
                }
            ],
            "interestedSuppliers": [{"id": str(i)} for i in range(42)],
            "bidders": [],
        }
        rows = awards._extract_apc_award_record(detail, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["supplier"], "Powerband Projects Inc.")
        self.assertEqual(rows[0]["supplier_location"], "Red Deer, CA-AB")
        self.assertEqual(rows[0]["amount"], 35643.58)
        self.assertEqual(rows[0]["interested_suppliers"], 42)
        summary = awards.summarize_awards(rows)
        self.assertEqual(summary["avg_interested_suppliers"], 42.0)


class Phase1CreditsAndWatchlistTest(unittest.TestCase):
    def setUp(self):
        storage.clear_memory_credits()

    def tearDown(self):
        storage.clear_memory_credits()

    def test_bid_pack_webhook_credits_user_idempotently(self):
        secret = "whsec_pack_test"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_pack_1",
                        "mode": "payment",
                        "customer": "cus_pack_1",
                        "client_reference_id": "user-abc",
                        "customer_details": {"email": "ap@shop.ca"},
                        "metadata": {"wa_plan": "pack_3", "wa_credits": "3", "wa_user_id": "user-abc"},
                    }
                },
            }
        ).encode()
        header = make_signature(payload, secret)
        env = {"STRIPE_WEBHOOK_SECRET": secret, "WA_OAUTH_STORE": "memory"}
        with mock.patch.dict(os.environ, env, clear=True):
            first = billing.process_webhook_event(payload, header)
            second = billing.process_webhook_event(payload, header)
        self.assertTrue(first["provisioned"])
        self.assertEqual(first["kind"], "bid_pack")
        self.assertEqual(first["credits_added"], 3)
        self.assertEqual(first["paid_credits"], 3)
        self.assertFalse(second["provisioned"])
        self.assertEqual(storage.get_user_credits("user-abc")["paid_credits"], 3)

    def test_credit_consumption_skips_errors_and_apc_upload_links(self):
        from procurement_core import identity

        record = {
            "auth_type": "oauth",
            "user_id": "user-trial-1",
            "email": "shop@example.ca",
            "pro_active": False,
            "credits_remaining": 2,
        }
        # Error output must never burn a credit.
        self.assertEqual(
            identity.consume_pro_credit_if_needed("classify_tender", record, text="Error: failed"),
            "",
        )
        # APC upload link step must never burn a credit.
        self.assertEqual(
            identity.consume_pro_credit_if_needed(
                "classify_tender", record, text="Upload link", structured={"upload_required": True}
            ),
            "",
        )
        self.assertEqual(storage.get_user_credits("user-trial-1")["free_credits_used"], 0)
        # Real completed run burns 1 free credit and appends remaining balance.
        footer1 = identity.consume_pro_credit_if_needed("classify_tender", record, text="# Requirements")
        self.assertIn("1 tender credit remaining", footer1)
        footer2 = identity.consume_pro_credit_if_needed("classify_tender", record, text="# Requirements")
        self.assertIn("0 credits remaining", footer2)
        self.assertEqual(storage.get_user_credits("user-trial-1")["free_credits_used"], 2)

    def test_free_watchlist_limit_enforced_for_non_pro_and_unlimited_for_pro(self):
        import asyncio
        from procurement_core import extensions

        existing = [{"reference": f"AB-2026-0000{i}"} for i in range(auth.FREE_WATCHLIST_LIMIT)]
        free_rec = {"user_id": "u1", "email": "free@shop.ca", "pro_active": False}
        pro_rec = {"user_id": "u2", "email": "pro@shop.ca", "pro_active": True}

        tok = storage.set_tenant_record(free_rec)
        try:
            with mock.patch.object(extensions, "load_watchlist", return_value=list(existing)):
                with mock.patch.object(extensions, "save_watchlist") as save_mock:
                    msg = asyncio.run(extensions.watch_opportunity({"reference": "AB-2026-99999"}))
            self.assertIn("free watchlist is full", msg.lower())
            save_mock.assert_not_called()
        finally:
            storage.reset_tenant_record(tok)

        tok = storage.set_tenant_record(pro_rec)
        try:
            with mock.patch.object(extensions, "load_watchlist", return_value=list(existing)):
                with mock.patch.object(extensions, "_find_opportunity", return_value=(None, [])):
                    with mock.patch.object(extensions, "save_watchlist") as save_mock:
                        msg = asyncio.run(extensions.watch_opportunity({"reference": "AB-2026-99999"}))
            self.assertIn("Watching `AB-2026-99999`", msg)
            save_mock.assert_called_once()
        finally:
            storage.reset_tenant_record(tok)


if __name__ == "__main__":
    unittest.main()
