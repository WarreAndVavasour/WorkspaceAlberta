"""OAuth 2.1 metadata, DCR, PKCE, 401 challenge, and Pro gating tests."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")
os.environ.setdefault("WA_OAUTH_STORE", "memory")
os.environ.setdefault("WA_OAUTH_SIGNING_KEY", "test-oauth-signing-key")
os.environ.setdefault("WA_OAUTH_DEV_SHOW_CODE", "1")

from procurement_core import auth, identity, oauth, storage  # noqa: E402


CANONICAL = "https://elbowsupknivesout.warreandvavasour.com/mcp"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = oauth._b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _register_claude() -> dict:
    return oauth.register_client(
        {
            "client_name": "Claude",
            "redirect_uris": [
                "https://claude.ai/api/mcp/auth_callback",
                "https://claude.com/api/mcp/auth_callback",
                "http://127.0.0.1/callback",
                "http://localhost/callback",
            ],
            "token_endpoint_auth_method": "none",
        }
    )


class MetadataTest(unittest.TestCase):
    def test_protected_resource_is_canonical(self):
        doc = oauth.protected_resource_metadata()
        self.assertEqual(doc["resource"], CANONICAL)
        self.assertEqual(doc["authorization_servers"], [oauth.DEFAULT_PUBLIC_ORIGIN])
        self.assertEqual(doc["scopes_supported"], ["pro"])
        self.assertEqual(doc["bearer_methods_supported"], ["header"])

    def test_authorization_server_advertises_pkce_dcr_and_cimd(self):
        doc = oauth.authorization_server_metadata()
        self.assertEqual(doc["issuer"], oauth.DEFAULT_PUBLIC_ORIGIN)
        self.assertTrue(doc["authorization_endpoint"].endswith("/authorize"))
        self.assertTrue(doc["token_endpoint"].endswith("/token"))
        self.assertTrue(doc["registration_endpoint"].endswith("/register"))
        self.assertEqual(doc["code_challenge_methods_supported"], ["S256"])
        self.assertIn("authorization_code", doc["grant_types_supported"])
        self.assertIn("refresh_token", doc["grant_types_supported"])
        self.assertIn("none", doc["token_endpoint_auth_methods_supported"])
        self.assertTrue(doc["client_id_metadata_document_supported"])
        self.assertIn("offline_access", doc["scopes_supported"])

    def test_www_authenticate_points_at_path_suffixed_prm(self):
        header = oauth.www_authenticate_challenge()
        self.assertIn("Bearer", header)
        self.assertIn(
            'resource_metadata="https://elbowsupknivesout.warreandvavasour.com/.well-known/oauth-protected-resource/mcp"',
            header,
        )
        self.assertIn('scope="pro"', header)


class RedirectUriTest(unittest.TestCase):
    def test_claude_and_loopback_allowed(self):
        self.assertTrue(oauth.redirect_uri_allowed("https://claude.ai/api/mcp/auth_callback"))
        self.assertTrue(oauth.redirect_uri_allowed("https://claude.com/api/mcp/auth_callback"))
        self.assertTrue(oauth.redirect_uri_allowed("http://localhost:3118/callback"))
        self.assertTrue(oauth.redirect_uri_allowed("http://127.0.0.1:48221/callback"))
        self.assertFalse(oauth.redirect_uri_allowed("https://evil.example/callback"))

    def test_loopback_matches_any_port(self):
        registered = ["http://localhost/callback", "http://127.0.0.1/callback"]
        self.assertTrue(oauth.redirect_uri_matches("http://localhost:3118/callback", registered))
        self.assertTrue(oauth.redirect_uri_matches("http://127.0.0.1:9/callback", registered))
        self.assertFalse(oauth.redirect_uri_matches("http://localhost:3118/other", registered))


class DynamicClientRegistrationTest(unittest.TestCase):
    def setUp(self):
        oauth.reset_oauth_state()

    def test_register_accepts_claude_redirects(self):
        created = _register_claude()
        self.assertTrue(created["client_id"].startswith(oauth.CLIENT_PREFIX))
        self.assertEqual(created["token_endpoint_auth_method"], "none")

    def test_register_rejects_foreign_redirect(self):
        with self.assertRaises(oauth.OAuthError) as ctx:
            oauth.register_client(
                {"redirect_uris": ["https://attacker.example/callback"]}
            )
        self.assertEqual(ctx.exception.error, "invalid_redirect_uri")


class PkceFlowTest(unittest.TestCase):
    def setUp(self):
        oauth.reset_oauth_state()
        identity.set_subscriber_lookup(None)

    def tearDown(self):
        identity.set_subscriber_lookup(None)
        oauth.reset_oauth_state()

    def _issue_tokens(self) -> dict:
        client = _register_claude()
        verifier, challenge = _pkce()
        params = oauth.validate_authorize_params(
            {
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "abc",
                "resource": CANONICAL,
                "scope": "pro",
            }
        )
        started = oauth.start_login("Owner@Shop.ca", params)
        self.assertIn("dev_code", started)
        verified = oauth.verify_login(started["login_id"], started["dev_code"])
        consented = oauth.take_consent(verified["consent_id"])
        code = oauth.issue_authorization_code(consented["user"], params)
        return oauth.issue_tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": client["client_id"],
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "resource": CANONICAL,
            }
        ), consented["user"]

    def test_pkce_issues_audience_bound_tokens(self):
        tokens, user = self._issue_tokens()
        self.assertTrue(tokens["access_token"].startswith(oauth.ACCESS_PREFIX))
        self.assertTrue(tokens["refresh_token"].startswith(oauth.REFRESH_PREFIX))
        claims = oauth.validate_access_token(tokens["access_token"])
        self.assertEqual(claims["aud"], CANONICAL)
        self.assertEqual(claims["email"], "owner@shop.ca")
        self.assertEqual(claims["sub"], user["id"])

    def test_wrong_verifier_is_invalid_grant(self):
        client = _register_claude()
        verifier, challenge = _pkce()
        params = oauth.validate_authorize_params(
            {
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": CANONICAL,
            }
        )
        started = oauth.start_login("owner@shop.ca", params)
        verified = oauth.verify_login(started["login_id"], started["dev_code"])
        consented = oauth.take_consent(verified["consent_id"])
        code = oauth.issue_authorization_code(consented["user"], params)
        with self.assertRaises(oauth.OAuthError) as ctx:
            oauth.issue_tokens(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": "this-is-not-the-verifier-and-is-long-enough",
                    "client_id": client["client_id"],
                    "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                    "resource": CANONICAL,
                }
            )
        self.assertEqual(ctx.exception.error, "invalid_grant")

    def test_refresh_rotates(self):
        tokens, _user = self._issue_tokens()
        refreshed = oauth.issue_tokens(
            {
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
            }
        )
        self.assertNotEqual(refreshed["refresh_token"], tokens["refresh_token"])
        with self.assertRaises(oauth.OAuthError) as ctx:
            oauth.issue_tokens(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                }
            )
        self.assertEqual(ctx.exception.error, "invalid_grant")

    def test_wrong_audience_rejected(self):
        tokens, _user = self._issue_tokens()
        with mock.patch.object(oauth, "public_mcp_resource", return_value="https://other.example/mcp"):
            with self.assertRaises(auth.GateError) as ctx:
                oauth.validate_access_token(tokens["access_token"])
        self.assertEqual(ctx.exception.status_code, 401)

    def test_cimd_client_and_loopback_port(self):
        client_id = "https://claude.ai/oauth/client-metadata.json"

        def fetch(url: str) -> dict:
            self.assertEqual(url, client_id)
            return {
                "client_id": client_id,
                "client_name": "Claude",
                "redirect_uris": ["http://localhost/callback", "http://127.0.0.1/callback"],
            }

        oauth.set_cimd_fetch(fetch)
        try:
            params = oauth.validate_authorize_params(
                {
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": "http://localhost:4242/callback",
                    "code_challenge": "a" * 43,
                    "code_challenge_method": "S256",
                    "resource": CANONICAL,
                }
            )
        finally:
            oauth.set_cimd_fetch(None)
        self.assertEqual(params["cimd"], "1")


class ProGatingTest(unittest.TestCase):
    def setUp(self):
        oauth.reset_oauth_state()
        auth.clear_cache()
        identity.set_subscriber_lookup(None)

    def tearDown(self):
        identity.set_subscriber_lookup(None)
        auth.clear_cache()
        oauth.reset_oauth_state()

    def test_oauth_without_subscription_is_402(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        tokens, _user = PkceFlowTest()._issue_tokens()
        identity.set_subscriber_lookup(lambda email: None)
        with mock.patch.dict(os.environ, env, clear=False):
            with self.assertRaises(auth.GateError) as ctx:
                identity.check_tool_access("list_watchlist", f"Bearer {tokens['access_token']}")
        self.assertEqual(ctx.exception.status_code, 402)

    def test_oauth_with_active_subscription_passes(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        tokens, user = PkceFlowTest()._issue_tokens()
        identity.set_subscriber_lookup(
            lambda email: {
                "email": email,
                "status": "active",
                "plan": "pro",
                "key_hash": "abc",
            }
        )
        with mock.patch.dict(os.environ, env, clear=False):
            record = identity.check_tool_access(
                "list_watchlist", f"Bearer {tokens['access_token']}"
            )
        self.assertTrue(record["pro_active"])
        self.assertEqual(record["auth_type"], "oauth")
        self.assertEqual(record["tenant_id"], f"user:{user['id']}")

    def test_legacy_key_still_works(self):
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        key = auth.generate_api_key()
        record = {"key_hash": auth.hash_api_key(key), "status": "active", "plan": "pro"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(auth, "_supabase_lookup", return_value=record):
                result = identity.check_tool_access("list_watchlist", f"Bearer {key}")
        self.assertEqual(result["auth_type"], "api_key")
        self.assertTrue(result["pro_active"])


class HostedAnonymousProfileTest(unittest.TestCase):
    def test_hosted_anonymous_does_not_share_a_file(self):
        from procurement_core import service

        with mock.patch.dict(os.environ, {"WA_HOSTED": "1"}, clear=False):
            self.assertFalse(storage.allow_anonymous_file_persist())
            self.assertEqual(service.load_profile(), {})
            self.assertFalse(service.save_profile({"company_name": "Should Not Persist"}))
            self.assertEqual(service.load_profile(), {})


class HttpOAuthTest(unittest.TestCase):
    def setUp(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("fastapi testclient unavailable")
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        import server_http

        oauth.reset_oauth_state()
        auth.clear_cache()
        identity.set_subscriber_lookup(None)
        self.client_context = TestClient(server_http.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        identity.set_subscriber_lookup(None)
        auth.clear_cache()
        oauth.reset_oauth_state()

    def test_metadata_endpoints(self):
        prm = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(prm.status_code, 200)
        self.assertEqual(prm.json()["resource"], CANONICAL)
        suffixed = self.client.get("/.well-known/oauth-protected-resource/mcp")
        self.assertEqual(suffixed.json(), prm.json())
        as_meta = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(as_meta.status_code, 200)
        self.assertEqual(as_meta.json()["grant_types_supported"], ["authorization_code", "refresh_token"])
        self.assertTrue(as_meta.json()["client_id_metadata_document_supported"])

    def test_dcr_http(self):
        created = self.client.post(
            "/register",
            json={
                "client_name": "Claude",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            },
        )
        self.assertEqual(created.status_code, 201)
        rejected = self.client.post(
            "/register",
            json={"redirect_uris": ["https://evil.example/cb"]},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.json()["error"], "invalid_redirect_uri")

    def test_pkce_http_flow(self):
        created = self.client.post(
            "/register",
            json={
                "client_name": "Claude",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            },
        ).json()
        verifier, challenge = _pkce()
        query = {
            "response_type": "code",
            "client_id": created["client_id"],
            "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
            "resource": CANONICAL,
            "scope": "pro",
        }
        page = self.client.get("/authorize", params=query)
        self.assertEqual(page.status_code, 200)
        self.assertIn("workspaceAlberta", page.text)
        emailed = self.client.post("/authorize", data={**query, "email": "owner@shop.ca"})
        self.assertEqual(emailed.status_code, 200)
        match = re.search(r'data-otp="(\d{6})"', emailed.text)
        self.assertIsNotNone(match)
        login_id = re.search(r'name="login_id" value="([^"]+)"', emailed.text).group(1)
        verified = self.client.post(
            "/authorize/verify",
            data={"login_id": login_id, "code": match.group(1)},
        )
        self.assertEqual(verified.status_code, 200)
        consent_id = re.search(r'name="consent_id" value="([^"]+)"', verified.text).group(1)
        approved = self.client.post(
            "/authorize/consent",
            data={"consent_id": consent_id, "decision": "approve"},
            follow_redirects=False,
        )
        self.assertEqual(approved.status_code, 302)
        location = urlparse(approved.headers["location"])
        self.assertEqual(location.hostname, "claude.ai")
        code = parse_qs(location.query)["code"][0]
        self.assertEqual(parse_qs(location.query)["state"][0], "xyz")
        tokens = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "client_id": created["client_id"],
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "resource": CANONICAL,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(tokens.status_code, 200)
        body = tokens.json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        me = self.client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "owner@shop.ca")
        self.assertEqual(me.json()["auth_type"], "oauth")

        # A signed-in customer without Pro needs billing guidance, not another
        # OAuth prompt; both the transport and the MCP result must reflect that.
        env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}
        identity.set_subscriber_lookup(lambda email: None)
        with mock.patch.dict(os.environ, env, clear=False):
            denied = self.client.post(
                "/mcp",
                headers={"Accept": "application/json", "Authorization": f"Bearer {body['access_token']}"},
                json={"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                      "params": {"name": "list_watchlist", "arguments": {}}},
            )
            self.assertEqual(denied.status_code, 200)
            self.assertNotIn("www-authenticate", denied.headers)
            self.assertTrue(denied.json()["result"]["isError"])
            self.assertIn("not active", denied.json()["result"]["content"][0]["text"])

        refresh_form = {"grant_type": "refresh_token", "refresh_token": body["refresh_token"],
                        "client_id": created["client_id"], "resource": CANONICAL}
        refreshed = self.client.post("/token", data=refresh_form)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.headers["cache-control"], "no-store")
        self.assertNotEqual(refreshed.json()["refresh_token"], body["refresh_token"])
        replayed = self.client.post("/token", data=refresh_form)
        self.assertEqual(replayed.status_code, 400)
        self.assertEqual(replayed.json()["error"], "invalid_grant")

    def test_pro_tool_401_challenge_rest_and_mcp(self):
        env = {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "k",
            "WA_OAUTH_STORE": "memory",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            rest = self.client.post("/tools/list_watchlist", json={})
            self.assertEqual(rest.status_code, 401)
            self.assertIn("resource_metadata=", rest.headers["www-authenticate"])
            mcp = self.client.post(
                "/mcp",
                headers={"Accept": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 9,
                    "method": "tools/call",
                    "params": {"name": "list_watchlist", "arguments": {}},
                },
            )
            self.assertEqual(mcp.status_code, 401)
            self.assertIn("resource_metadata=", mcp.headers["www-authenticate"])
            self.assertEqual(mcp.json()["error"], "invalid_token")
            free = self.client.post(
                "/mcp",
                headers={"Accept": "application/json"},
                json={"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
            )
            self.assertEqual(free.status_code, 200)
            self.assertIn("tools", free.json()["result"])


if __name__ == "__main__":
    unittest.main()
