"""Google upstream identity and the complete downstream MCP PKCE boundary."""
import hashlib
import json
import os
import re
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.auth import crypt, jwt
from procurement_core import google_login, oauth, oauth_http

CONFIG = {"WA_LOGIN_PROVIDER": "google", "WA_GOOGLE_CLIENT_ID": "test.apps.googleusercontent.com",
          "WA_GOOGLE_CLIENT_SECRET": "test-only", "WA_OAUTH_SIGNING_KEY": "s" * 48,
          "WA_PUBLIC_ORIGIN": "https://testserver", "WA_PUBLIC_MCP_URL": "https://testserver/mcp"}


class GoogleFlowTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, CONFIG)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = oauth.MemoryOAuthStore()
        oauth.use_store(self.store)
        self.addCleanup(oauth.use_store, None)
        self.client = oauth.register_client({"client_name": "Test MCP client",
                                             "redirect_uris": ["http://localhost/callback"]})
        self.verifier = "v" * 43
        self.params = {"response_type": "code", "client_id": self.client["client_id"],
                       "redirect_uri": "http://localhost:3218/callback", "state": "mcp-client-state",
                       "resource": "https://testserver/mcp", "scope": "pro offline_access",
                       "code_challenge_method": "S256",
                       "code_challenge": oauth._b64url(hashlib.sha256(self.verifier.encode()).digest())}
        app = FastAPI()
        oauth_http.register_oauth_routes(app)
        self.http = TestClient(app, base_url="https://testserver", follow_redirects=False)
        self.addCleanup(self.http.close)

    def begin(self):
        response = self.http.post("/authorize/google", data=self.params)
        self.assertEqual(response.status_code, 303)
        query = {k: v[0] for k, v in parse_qs(urlparse(response.headers["location"]).query).items()}
        self.assertEqual(query["scope"], "openid email")
        self.assertEqual(query["redirect_uri"], "https://testserver/oauth/google/callback")
        self.assertEqual(query["code_challenge_method"], "S256")
        self.assertIn("Secure", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        return query

    def callback(self, query, **claims):
        identity = {"sub": "google-subject-1", "email": "owner@gmail.com", "email_verified": True,
                    "nonce": query["nonce"], **claims}
        with patch.object(google_login, "exchange_and_verify", return_value=identity):
            return self.http.get("/oauth/google/callback", params={"state": query["state"], "code": "test-code"})

    def test_google_login_consent_pkce_refresh_and_replays(self):
        page = self.http.get("/authorize", params=self.params)
        self.assertIn("Continue with Google", page.text)
        self.assertNotIn('type="email"', page.text)
        query = self.begin()
        consent = self.callback(query)
        self.assertEqual(consent.status_code, 200)
        self.assertEqual(consent.headers["cache-control"], "no-store")
        self.assertEqual(consent.headers["referrer-policy"], "no-referrer")
        consent_id = re.search(r'name="consent_id" value="([^"]+)"', consent.text)[1]
        redirect = self.http.post("/authorize/consent", data={"consent_id": consent_id, "decision": "approve"})
        grant = parse_qs(urlparse(redirect.headers["location"]).query)
        self.assertEqual(grant["state"], ["mcp-client-state"])
        form = {"grant_type": "authorization_code", "code": grant["code"][0], "code_verifier": self.verifier,
                "client_id": self.client["client_id"], "redirect_uri": self.params["redirect_uri"],
                "resource": self.params["resource"]}
        tokens = self.http.post("/token", data=form).json()
        self.assertEqual(oauth.validate_access_token(tokens["access_token"])["email"], "owner@gmail.com")
        self.assertEqual(self.http.post("/token", data=form).status_code, 400)
        refresh = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                   "client_id": self.client["client_id"], "resource": self.params["resource"]}
        self.assertEqual(self.http.post("/token", data=refresh).status_code, 200)
        self.assertEqual(self.http.post("/token", data=refresh).status_code, 400)
        self.assertEqual(self.callback(query).status_code, 400)
        self.assertEqual(self.http.post("/authorize/consent", data={"consent_id": consent_id, "decision": "approve"}).status_code, 400)

    def test_wrong_browser_cannot_consume_state_or_redeem_consent(self):
        query = self.begin()
        cookie = self.http.cookies.get(google_login.BROWSER_COOKIE)
        self.http.cookies.clear()
        self.assertEqual(self.callback(query).status_code, 400)
        self.http.cookies.set(google_login.BROWSER_COOKIE, cookie)
        consent = self.callback(query)
        self.assertEqual(consent.status_code, 200)
        consent_id = re.search(r'name="consent_id" value="([^"]+)"', consent.text)[1]
        self.http.cookies.clear()
        self.assertEqual(self.http.post("/authorize/consent", data={"consent_id": consent_id, "decision": "approve"}).status_code, 400)

    def test_identity_and_nonce_rejections(self):
        for invalid in [{"nonce": "wrong"}, {"email_verified": False}, {"sub": ""},
                        {"email": "owner@third-party.example"}]:
            with self.subTest(invalid=invalid):
                query = self.begin()
                self.assertEqual(self.callback(query, **invalid).status_code, 400)
                self.assertEqual(self.callback(query).status_code, 400)
        self.assertFalse(self.store.users)

    def test_workspace_email_supported(self):
        self.assertEqual(self.callback(self.begin(), email="owner@business.example", hd="business.example").status_code, 200)

    def test_expired_state_and_provider_denial(self):
        query = self.begin()
        self.store.google_states[oauth._hash_secret(query["state"])]["expires_at"] = oauth._iso(oauth._utc_now() - timedelta(seconds=1))
        self.assertEqual(self.callback(query).status_code, 400)
        query = self.begin()
        with patch.object(google_login, "exchange_and_verify") as exchange:
            self.assertEqual(self.http.get("/oauth/google/callback", params={"state": query["state"], "error": "access_denied"}).status_code, 400)
            exchange.assert_not_called()

    def test_google_only_mode_disables_email_endpoints(self):
        with patch.object(oauth, "send_login_code") as send:
            self.assertEqual(self.http.post("/authorize", data=self.params).status_code, 404)
            self.assertEqual(self.http.post("/authorize/verify", data={"code": "123456"}).status_code, 404)
            send.assert_not_called()

    def test_google_subject_is_stable_and_email_never_merges_accounts(self):
        one = self.store.google_user("one", "one@gmail.com")
        self.assertEqual(self.store.google_user("one", "renamed@gmail.com")["id"], one["id"])
        self.store.upsert_user("legacy@gmail.com")
        for subject, email in [("two", "renamed@gmail.com"), ("two", "legacy@gmail.com")]:
            with self.assertRaises(oauth.OAuthError):
                self.store.google_user(subject, email)

    def test_concurrent_state_has_one_winner(self):
        query = self.begin()
        state_hash = oauth._hash_secret(query["state"])
        browser_hash = oauth._hash_secret(self.http.cookies.get(google_login.BROWSER_COOKIE))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.store.take_google_state(state_hash, browser_hash), range(8)))
        self.assertEqual(sum(row is not None for row in results), 1)

    def test_google_hosted_configuration_needs_no_smtp(self):
        config = {**CONFIG, "K_SERVICE": "test", "SUPABASE_URL": "https://test.supabase.co",
                  "SUPABASE_SERVICE_ROLE_KEY": "test"}
        with patch.dict(os.environ, config, clear=True):
            oauth.validate_hosted_configuration()
        for missing in ["WA_GOOGLE_CLIENT_ID", "WA_GOOGLE_CLIENT_SECRET"]:
            with patch.dict(os.environ, {**config, missing: ""}, clear=True), self.assertRaises(RuntimeError):
                oauth.validate_hosted_configuration()


class GoogleTokenVerificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.signer = crypt.RSASigner.from_string(private, key_id="test")
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def test_real_library_checks_signature_audience_issuer_and_expiry(self):
        claims = {"iss": "https://accounts.google.com", "aud": CONFIG["WA_GOOGLE_CLIENT_ID"],
                  "sub": "12345", "iat": int(time.time()) - 5, "exp": int(time.time()) + 600}
        for overrides in [{}, {"iss": "https://evil.example"}, {"aud": "another-client"}, {"exp": int(time.time()) - 100}]:
            with self.subTest(overrides=overrides), patch.dict(os.environ, CONFIG):
                token = jwt.encode(self.signer, {**claims, **overrides}).decode()
                session = MagicMock()
                session.post.return_value.status_code = 200
                session.post.return_value.json.return_value = {"id_token": token}
                transport = MagicMock(return_value=SimpleNamespace(status=200, data=json.dumps({"test": self.public}).encode()))
                with patch.object(google_login.requests, "Session") as factory, patch.object(google_login, "Request", return_value=transport):
                    factory.return_value.__enter__.return_value = session
                    if overrides:
                        with self.assertRaises(oauth.OAuthError):
                            google_login.exchange_and_verify("code", "verifier")
                    else:
                        self.assertEqual(google_login.exchange_and_verify("code", "verifier")["sub"], "12345")
                        session.post.assert_called_once()
                        self.assertEqual(transport.call_args.kwargs["timeout"], 5)
        bad_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        bad_public = bad_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        transport.return_value.data = json.dumps({"test": bad_public}).encode()
        with patch.dict(os.environ, CONFIG), patch.object(google_login.requests, "Session") as factory, patch.object(google_login, "Request", return_value=transport):
            factory.return_value.__enter__.return_value = session
            session.post.return_value.json.return_value = {"id_token": jwt.encode(self.signer, claims).decode()}
            with self.assertRaises(oauth.OAuthError):
                google_login.exchange_and_verify("code", "verifier")


if __name__ == "__main__":
    unittest.main()
