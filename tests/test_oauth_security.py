"""Regression tests for browser output, shared grant state, and CIMD transport."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from procurement_core import oauth, oauth_http
from procurement_core.auth_pages import ARTWORK


class ParsedHTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class OAuthHTMLTest(unittest.TestCase):
    def test_untrusted_values_stay_text_and_attribute_values(self):
        attack = '\"><script>alert(1)</script><img src=x onerror=alert(2)>'
        pages = [
            oauth_http._email_form({"state": attack, "redirect_uri": attack}, error=attack, notice=attack),
            oauth_http._code_form(attack, attack, dev_code=attack, error=attack),
            oauth_http._consent_form({"authorize_params": {"client_name": attack, "redirect_uri": attack},
                                      "user": {"email": attack}, "consent_id": attack}),
            oauth_http._page(attack, "<p>Trusted markup</p>"),
        ]
        for page in pages:
            tags = ParsedHTML(page).tags
            self.assertFalse(any(t == "script" for t, _ in tags))
            allowed_images = {f"/assets/archive/{scan}.webp" for scan, *_ in ARTWORK}
            self.assertTrue(all(attrs.get("src") in allowed_images
                                for tag, attrs in tags if tag == "img"))
            self.assertFalse(any(k.startswith("on") for _, attrs in tags for k in attrs))
        self.assertEqual(dict((a.get("name"), a.get("value")) for t, a in
                              ParsedHTML(pages[1]).tags if t == "input")["login_id"], attack)

    def test_archive_files_match_allowlist_and_every_piece_renders(self):
        # The Cloud Run release check requires every served archive file on the sign-in page.
        archive = Path(oauth_http.__file__).with_name("assets") / "archive"
        stems = [scan for scan, *_ in ARTWORK]
        self.assertEqual(len(stems), len(set(stems)))
        self.assertEqual({path.stem for path in archive.glob("*.webp")}, set(stems))
        page = oauth_http._google_form({"redirect_uri": "https://client.example/callback"})
        for stem in stems:
            self.assertIn(f"/assets/archive/{stem}.webp", page)

    def test_reflected_login_and_backend_error_are_escaped(self):
        app = FastAPI()
        oauth_http.register_oauth_routes(app)
        attack = '\"><svg onload=alert(1)>'
        with TestClient(app) as client, patch.object(oauth, "verify_login", side_effect=
                oauth.OAuthError(400, "invalid_request", attack)):
            response = client.post("/authorize/verify", data={"login_id": attack, "code": "000000"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(any(tag == "svg" for tag, _ in ParsedHTML(response.text).tags))

    def test_deny_consumes_consent(self):
        app = FastAPI()
        oauth_http.register_oauth_routes(app)
        store = RestFixture()
        store.put_login({"id": "deny", "code_hash": oauth._hash_secret("consent"),
                         "expires_at": oauth._iso(oauth._utc_now() + timedelta(minutes=5)),
                         "authorize_params": {"user_id": "test", "email": "test@example.invalid",
                                              "redirect_uri": "http://localhost/callback"}})
        with TestClient(app) as client, patch.object(oauth, "get_store", return_value=store):
            self.assertEqual(client.post("/authorize/consent", data={"consent_id": "deny", "decision": "deny"},
                                         follow_redirects=False).status_code, 302)
            self.assertEqual(client.post("/authorize/consent", data={"consent_id": "deny", "decision": "approve"},
                                         follow_redirects=False).status_code, 400)


class HostedConfigurationTest(unittest.TestCase):
    def test_hosted_requires_persistence_signing_and_email_without_debug_codes(self):
        config = {"K_SERVICE": "test", "WA_OAUTH_SIGNING_KEY": "x" * 48,
                  "SUPABASE_URL": "https://test.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "test",
                  "WA_SMTP_HOST": "smtp.example.com", "WA_SMTP_FROM": "login@example.com"}
        with patch.dict(os.environ, config, clear=True):
            oauth.validate_hosted_configuration()
        for broken in [{"WA_OAUTH_SIGNING_KEY": ""}, {"WA_SMTP_HOST": ""}, {"WA_SMTP_FROM": ""},
                       {"WA_OAUTH_DEV_SHOW_CODE": "1"}, {"WA_OAUTH_STORE": "memory"},
                       {"WA_OAUTH_STORE": " memory "},
                       {"SUPABASE_SERVICE_ROLE_KEY": ""}, {"WA_SMTP_STARTTLS": "0"}]:
            with self.subTest(broken=list(broken)), patch.dict(os.environ, {**config, **broken}, clear=True):
                with self.assertRaises(RuntimeError):
                    oauth.validate_hosted_configuration()


class RestFixture(oauth.SupabaseOAuthStore):
    """PostgREST row/filter semantics, including returned post-update timestamps."""
    def __init__(self):
        self.tables = {}
        self.lock = threading.Lock()

    def _request(self, method, path_query, payload=None, prefer="return=representation"):
        table, _, query = path_query.partition("?")
        filters = parse_qs(query)
        with self.lock:
            rows = self.tables.setdefault(table, [])
            if method == "POST":
                rows.extend(copy.deepcopy(payload))
                return copy.deepcopy(payload)
            matched = [row for row in rows if all(
                key in {"select", "limit"} or
                (value[0] == "is.null" and row.get(key) is None) or
                (value[0].startswith("eq.") and str(row.get(key)) == value[0][3:])
                for key, value in filters.items())]
            if method == "PATCH":
                for row in matched:
                    row.update(payload)
            elif method != "GET":
                raise AssertionError(method)
            return copy.deepcopy(matched) if prefer != "return=minimal" else None


def concurrent(call, count=8):
    barrier = threading.Barrier(count)
    def run(_):
        barrier.wait(timeout=10)
        try:
            return call()
        except oauth.OAuthError:
            return None
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


class GrantConsumptionTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"WA_OAUTH_SIGNING_KEY": "test-only", "WA_OAUTH_DEV_SHOW_CODE": "1"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(oauth.use_store, None)

    def stores(self):
        return [oauth.MemoryOAuthStore(), RestFixture()]

    def test_authorization_code_issues_only_one_token_pair(self):
        for store in self.stores():
            with self.subTest(store=type(store).__name__):
                oauth.use_store(store)
                client = oauth.register_client({"redirect_uris": ["http://localhost/callback"]})
                verifier = "a" * 64
                params = {"client_id": client["client_id"], "redirect_uri": "http://localhost/callback",
                          "resource": oauth.public_mcp_resource(),
                          "code_challenge": oauth._b64url(hashlib.sha256(verifier.encode()).digest())}
                code = oauth.issue_authorization_code({"id": "test", "email": "test@example.invalid"}, params)
                form = {**params, "code": code, "code_verifier": verifier, "grant_type": "authorization_code"}
                outcomes = concurrent(lambda: oauth.issue_tokens(form))
                self.assertEqual(sum(x is not None for x in outcomes), 1)
                winner = next(x for x in outcomes if x)
                self.assertEqual(oauth.validate_access_token(winner["access_token"])["sub"], "test")

    def test_refresh_one_winner_and_wrong_client_does_not_burn_token(self):
        for store in self.stores():
            with self.subTest(store=type(store).__name__):
                oauth.use_store(store)
                original = oauth._issue_refresh_token({"id": "test", "email": "test@example.invalid"},
                                                       "client", oauth.public_mcp_resource(), "pro")
                form = {"grant_type": "refresh_token", "refresh_token": original}
                with self.assertRaises(oauth.OAuthError):
                    oauth.issue_tokens({**form, "client_id": "wrong-client"})
                outcomes = concurrent(lambda: oauth.issue_tokens(form))
                self.assertEqual(sum(x is not None for x in outcomes), 1)
                winner = next(x for x in outcomes if x)
                self.assertNotEqual(winner["refresh_token"], original)
                self.assertTrue(oauth.issue_tokens({**form, "refresh_token": winner["refresh_token"]}))

    def test_consent_is_consumed_once_and_otp_cannot_be_used_as_consent(self):
        for store in self.stores():
            with self.subTest(store=type(store).__name__):
                oauth.use_store(store)
                row = {"id": "consent", "code_hash": oauth._hash_secret("consent"),
                       "expires_at": oauth._iso(oauth._utc_now() + timedelta(minutes=10)),
                       "authorize_params": {"user_id": "test", "email": "test@example.invalid"}}
                store.put_login(row)
                outcomes = concurrent(lambda: oauth.take_consent("consent"))
                self.assertEqual(sum(x is not None for x in outcomes), 1)
                with self.assertRaises(oauth.OAuthError):
                    oauth.take_consent("consent")
                store.put_login({**row, "id": "otp", "code_hash": oauth._hash_secret("123456")})
                with self.assertRaises(oauth.OAuthError):
                    oauth.take_consent("otp")
                self.assertIsNotNone(store.get_login("otp"))

    def test_otp_one_winner_and_consent_cannot_be_renewed(self):
        oauth.use_store(oauth.MemoryOAuthStore())
        started = oauth.start_login("test@example.invalid", {})
        outcomes = concurrent(lambda: oauth.verify_login(started["login_id"], started["dev_code"]))
        self.assertEqual(sum(x is not None for x in outcomes), 1)
        consent = next(x for x in outcomes if x)
        with self.assertRaises(oauth.OAuthError):
            oauth.verify_login(consent["consent_id"], "consent")
        self.assertTrue(oauth.take_consent(consent["consent_id"]))

    def test_concurrent_wrong_codes_use_all_five_attempts(self):
        store = oauth.MemoryOAuthStore()
        oauth.use_store(store)
        started = oauth.start_login("test@example.invalid", {})
        concurrent(lambda: oauth.verify_login(started["login_id"], "wrong"), 12)
        self.assertEqual(store.get_login(started["login_id"])["attempts"], 5)
        with self.assertRaisesRegex(oauth.OAuthError, "Too many attempts"):
            oauth.verify_login(started["login_id"], started["dev_code"])


@unittest.skipUnless(os.environ.get("WA_OAUTH_TEST_SUPABASE") == "1", "explicit live database opt-in required")
class LiveSupabaseTest(GrantConsumptionTest):
    """Run against the configured project; create and remove only test-owned rows.

    WA_OAUTH_TEST_SUPABASE=1 python -m unittest tests.test_oauth_security.LiveSupabaseTest
    Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY, migrations 002 and 003.
    Does not send email, create subscribers, or change real user data.
    """
    def setUp(self):
        super().setUp()
        self.live = oauth.SupabaseOAuthStore()
        original = self.live._request
        created = []

        def tracked(method, path, payload=None, prefer="return=representation"):
            result = original(method, path, payload, prefer)
            if method == "POST" and not path.startswith("rpc/"):
                key = {"wa_oauth_clients": "client_id", "wa_oauth_auth_codes": "code_hash",
                       "wa_oauth_refresh_tokens": "token_hash", "wa_oauth_login_challenges": "id"}[path]
                created.extend((path, key, row[key]) for row in payload)
            return result

        def cleanup():
            for table, key, value in created:
                original("DELETE", table + "?" + urlencode({key: "eq." + value}), prefer="return=minimal")

        self.live._request = tracked
        self.addCleanup(cleanup)

    def stores(self):
        # Parent tests use fixed consent IDs; namespace them for concurrent runs.
        original_put, original_get = self.live.put_login, self.live.get_login
        original_take = self.live.take_consent
        prefix = "oauth-regression-" + uuid.uuid4().hex + "-"
        self.live.put_login = lambda row: original_put({**row, "id": prefix + row["id"],
                                                       "email": "test@example.invalid"})
        self.live.get_login = lambda key: original_get(prefix + key)
        self.live.take_consent = lambda key: original_take(prefix + key)
        return [self.live]

    def test_database_otp_lock_and_attempt_limit(self):
        for correct in [True, False]:
            key = "oauth-regression-" + uuid.uuid4().hex
            self.live.put_login({"id": key, "email": "test@example.invalid", "attempts": 0,
                                 "code_hash": oauth._hash_secret("123456"), "authorize_params": {},
                                 "expires_at": oauth._iso(oauth._utc_now() + timedelta(minutes=5))})
            hashed = oauth._hash_secret("123456" if correct else "wrong")
            results = concurrent(lambda: self.live.verify_login(key, hashed))
            self.assertEqual(sum("row" in x for x in results), 1 if correct else 0)
            if not correct:
                self.assertEqual(self.live.get_login(key)["attempts"], 5)
            self.assertIn("error", self.live.verify_login(key, oauth._hash_secret("123456")))

    def test_database_rejects_consent_as_otp(self):
        key = "oauth-regression-" + uuid.uuid4().hex
        self.live.put_login({"id": key, "email": "test@example.invalid", "attempts": 0,
                             "code_hash": oauth._hash_secret("consent"), "authorize_params": {},
                             "expires_at": oauth._iso(oauth._utc_now() + timedelta(minutes=5))})
        self.assertIn("error", self.live.verify_login(key, oauth._hash_secret("consent")))
        self.assertIsNotNone(self.live.take_consent(key))


@unittest.skipUnless(os.environ.get("WA_OAUTH_TEST_SUPABASE") == "1", "explicit live database opt-in required")
class LiveOAuthHttpTest(unittest.TestCase):
    """Exercise local HTTP routes with real persistence and a captured mail boundary.

    Uses a synthetic .invalid user and an ephemeral signing key. Does not send
    email or create a subscriber; removes every row created by this test.
    """

    def test_code_consent_pkce_and_refresh_with_real_database(self):
        live = oauth.SupabaseOAuthStore()
        original = live._request
        created = []

        def tracked(method, path, payload=None, prefer="return=representation"):
            result = original(method, path, payload, prefer)
            if method == "POST" and not path.startswith("rpc/"):
                key = {"wa_oauth_clients": "client_id", "wa_oauth_auth_codes": "code_hash",
                       "wa_oauth_refresh_tokens": "token_hash", "wa_oauth_login_challenges": "id",
                       "wa_users": "id"}[path]
                rows = result if path == "wa_users" else payload
                created.extend((path, key, row[key]) for row in rows)
            return result

        def cleanup():
            for table, key, value in reversed(created):
                query = urlencode({key: "eq." + value})
                original("DELETE", table + "?" + query, prefer="return=minimal")
                self.assertFalse(original("GET", table + "?" + query))

        live._request = tracked
        oauth.use_store(live)
        self.addCleanup(oauth.use_store, None)
        self.addCleanup(cleanup)
        app = FastAPI()
        oauth_http.register_oauth_routes(app)
        email = "oauth-http-" + uuid.uuid4().hex + "@example.invalid"
        verifier = oauth.secrets.token_urlsafe(64)
        resource = oauth.public_mcp_resource()

        def hidden(page, name):
            return next(attrs["value"] for tag, attrs in ParsedHTML(page).tags
                        if tag == "input" and attrs.get("name") == name)

        env = {"WA_OAUTH_DEV_SHOW_CODE": "0", "WA_OAUTH_SIGNING_KEY": oauth.secrets.token_urlsafe(48)}
        with patch.dict(os.environ, env), patch.object(oauth, "send_login_code", return_value=True) as mail, \
                TestClient(app) as client:
            registered = client.post("/register", json={"client_name": "OAuth HTTP verification",
                                     "redirect_uris": ["http://localhost/callback"]})
            self.assertEqual(registered.status_code, 201)
            client_id = registered.json()["client_id"]
            query = {"response_type": "code", "client_id": client_id,
                     "redirect_uri": "http://localhost:3118/callback", "resource": resource,
                     "code_challenge_method": "S256", "state": "http-test",
                     "code_challenge": oauth._b64url(hashlib.sha256(verifier.encode()).digest())}
            self.assertEqual(client.get("/authorize", params=query).status_code, 200)
            started = client.post("/authorize", data={**query, "email": email})
            self.assertEqual(started.status_code, 200)
            self.assertNotIn("data-otp=", started.text)
            self.assertEqual(mail.call_count, 1)
            self.assertEqual(mail.call_args.args[0], email)
            verified = client.post("/authorize/verify", data={"login_id": hidden(started.text, "login_id"),
                                   "code": mail.call_args.args[1]})
            self.assertEqual(verified.status_code, 200)
            approved = client.post("/authorize/consent", data={"consent_id": hidden(verified.text, "consent_id"),
                                   "decision": "approve"}, follow_redirects=False)
            self.assertEqual(approved.status_code, 302)
            returned = parse_qs(approved.headers["location"].split("?", 1)[1])
            self.assertEqual(returned["state"], ["http-test"])
            exchange = {"grant_type": "authorization_code", "client_id": client_id,
                        "redirect_uri": query["redirect_uri"], "code": returned["code"][0],
                        "code_verifier": verifier, "resource": resource}
            token_response = client.post("/token", data=exchange)
            self.assertEqual(token_response.status_code, 200)
            self.assertEqual(token_response.headers["cache-control"], "no-store")
            tokens = token_response.json()
            self.assertEqual(oauth.validate_access_token(tokens["access_token"])["email"], email)
            self.assertEqual(client.post("/token", data=exchange).json()["error"], "invalid_grant")
            refresh = {"grant_type": "refresh_token", "client_id": client_id,
                       "refresh_token": tokens["refresh_token"], "resource": resource}
            rotated = client.post("/token", data=refresh)
            self.assertEqual(rotated.status_code, 200)
            self.assertTrue(rotated.json()["refresh_token"] != tokens["refresh_token"])
            replay = client.post("/token", data=refresh)
            self.assertEqual(replay.status_code, 400)
            self.assertEqual(replay.json()["error"], "invalid_grant")


class CimdTransportTest(unittest.TestCase):
    URL = "https://client.example/metadata.json"
    PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    def setUp(self):
        # Isolate transport mocks from unrelated background HTTP/telemetry threads.
        network = SimpleNamespace(getaddrinfo=socket.getaddrinfo, socket=socket.socket,
                                  SOCK_STREAM=socket.SOCK_STREAM, gaierror=socket.gaierror)
        replacement = patch.object(oauth, "socket", network)
        replacement.start()
        self.addCleanup(replacement.stop)

    def test_rejects_nonpublic_empty_and_mixed_dns(self):
        for ips in [[], ["100.64.0.1"], ["127.0.0.1"], ["169.254.169.254"],
                    ["::1"], ["::ffff:127.0.0.1"], ["::ffff:100.64.0.1"],
                    ["2002:0a00:0001::"], ["64:ff9b::a00:1"], ["93.184.216.34", "10.0.0.1"]]:
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]
            with self.subTest(ips=ips), patch.object(oauth.socket, "getaddrinfo", return_value=answers), \
                    patch.object(oauth, "_PinnedHTTPSConnection") as connection:
                with self.assertRaises(oauth.OAuthError):
                    oauth._default_cimd_fetch(self.URL)
                connection.assert_not_called()

    def test_rejects_redirect_and_oversize_and_malformed_document(self):
        for status, body in [(302, b''), (200, b'x' * (oauth.CIMD_MAX_BYTES + 1)),
                             (200, b'[]'), (200, b'not json')]:
            with self.subTest(status=status, size=len(body)), \
                    patch.object(oauth.socket, "getaddrinfo", return_value=self.PUBLIC), \
                    patch.object(oauth, "_PinnedHTTPSConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status, response.read.return_value = status, body
                with self.assertRaises(oauth.OAuthError):
                    oauth._default_cimd_fetch(self.URL)
                self.assertEqual(connection.call_count, 1)
                self.assertEqual(connection.return_value.request.call_count, 1)
                connection.return_value.close.assert_called_once()

    def test_invalid_urls_never_connect(self):
        for url in ["http://client.example/doc", "https://user@client.example/doc",
                    "https://client.example/doc#fragment", "https://client.example:bad/doc",
                    "https://client.example/\nmetadata", "https://client.example/"]:
            with self.subTest(url=url), patch.object(oauth, "_PinnedHTTPSConnection") as connection:
                with self.assertRaises(oauth.OAuthError):
                    oauth._default_cimd_fetch(url)
                connection.assert_not_called()

    def test_connect_uses_checked_address_and_original_tls_hostname(self):
        with patch.object(oauth.socket, "socket") as sock, patch.object(oauth.socket, "getaddrinfo") as dns:
            connection = oauth._PinnedHTTPSConnection("client.example", 443, self.PUBLIC)
            self.assertTrue(connection._context.check_hostname)
            self.assertEqual(connection._context.verify_mode, oauth.ssl.CERT_REQUIRED)
            with patch.object(connection._context, "wrap_socket") as tls:
                connection.connect()
            dns.assert_not_called()
            sock.return_value.connect.assert_called_once_with(("93.184.216.34", 443))
            tls.assert_called_once_with(sock.return_value, server_hostname="client.example")

    def test_public_https_document_and_query_work(self):
        document = {"client_id": self.URL, "redirect_uris": ["http://localhost/callback"]}
        with patch.object(oauth.socket, "getaddrinfo", return_value=self.PUBLIC) as dns, \
                patch.object(oauth, "_PinnedHTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = json.dumps(document).encode()
            self.assertEqual(oauth._default_cimd_fetch(self.URL + "?v=1"), document)
            dns.assert_called_once()
            connection.assert_called_once_with("client.example", 443, self.PUBLIC)
            connection.return_value.request.assert_called_once_with(
                "GET", "/metadata.json?v=1", headers={"Accept": "application/json"})

    def test_unreachable_public_address_falls_back_without_resolving_again(self):
        addresses = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1111", 443, 0, 0))] + self.PUBLIC
        with patch.object(oauth.socket, "socket") as make_socket, patch.object(oauth.socket, "getaddrinfo") as dns:
            first, second = unittest.mock.Mock(), unittest.mock.Mock()
            first.connect.side_effect = OSError("IPv6 unavailable")
            make_socket.side_effect = [first, second]
            connection = oauth._PinnedHTTPSConnection("client.example", 443, addresses)
            with patch.object(connection._context, "wrap_socket") as tls:
                connection.connect()
            first.close.assert_called_once()
            second.connect.assert_called_once_with(("93.184.216.34", 443))
            tls.assert_called_once_with(second, server_hostname="client.example")
            dns.assert_not_called()


if __name__ == "__main__":
    unittest.main()
