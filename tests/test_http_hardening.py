"""HTTP hardening: baseline headers, MCP body limit, sign-in code limit, security events."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "mcp-servers" / "canadabuys"
TEST_DATA_DIR = tempfile.TemporaryDirectory()

os.environ.setdefault("CANADABUYS_DATA_DIR", TEST_DATA_DIR.name)
os.environ.setdefault("WA_OAUTH_STORE", "memory")
os.environ.setdefault("WA_OAUTH_SIGNING_KEY", "test-oauth-signing-key")
sys.path.insert(0, str(SERVER_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from server_http import app  # noqa: E402

from procurement_core import http_hardening, oauth  # noqa: E402

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _events(output: str, kind: str) -> list[dict]:
    lines = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    return [line for line in lines if line.get("event") == "security_event" and line.get("kind") == kind]


class BaselineHeadersTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self) -> None:
        self.context.__exit__(None, None, None)

    def test_every_response_gets_baseline_headers(self) -> None:
        for path in ("/health", "/tools", "/.well-known/mcp.json", "/no-such-page"):
            response = self.client.get(path)
            self.assertIn("max-age=31536000", response.headers["strict-transport-security"], path)
            self.assertEqual(response.headers["x-content-type-options"], "nosniff", path)
            self.assertEqual(response.headers["x-frame-options"], "DENY", path)
            self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"], path)

    def test_sign_in_pages_keep_their_stricter_policy(self) -> None:
        response = self.client.get("/authorize")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertTrue(response.headers["content-security-policy"].startswith("default-src 'none'"))
        self.assertEqual(response.headers.get_list("content-security-policy").__len__(), 1)

    def test_mcp_initialize_still_works(self) -> None:
        response = self.client.post("/mcp", headers=MCP_HEADERS, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["serverInfo"]["name"], "canadabuys")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")


class McpBodyLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self) -> None:
        self.context.__exit__(None, None, None)

    def test_oversized_body_is_refused_with_413_and_logged(self) -> None:
        with patch.dict(os.environ, {"WA_MAX_MCP_BODY_BYTES": "1024"}):
            out = io.StringIO()
            with redirect_stdout(out):
                response = self.client.post("/mcp", headers={**MCP_HEADERS, "Content-Type": "application/json"},
                                            content=b"{" + b" " * 4096 + b"}")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"], "request_too_large")
        self.assertEqual(len(_events(out.getvalue(), "mcp_body_too_large")), 1)

    def test_body_under_the_limit_is_served(self) -> None:
        with patch.dict(os.environ, {"WA_MAX_MCP_BODY_BYTES": "4096"}):
            response = self.client.post("/mcp", headers=MCP_HEADERS, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
            })
        self.assertEqual(response.status_code, 200)

    def test_invalid_limit_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"WA_MAX_MCP_BODY_BYTES": "abc"}):
            self.assertEqual(http_hardening.body_limit_bytes(), http_hardening.DEFAULT_MCP_BODY_LIMIT)
        with patch.dict(os.environ, {"WA_MAX_MCP_BODY_BYTES": "-5"}):
            self.assertEqual(http_hardening.body_limit_bytes(), http_hardening.DEFAULT_MCP_BODY_LIMIT)


class SlidingWindowLimiterTest(unittest.TestCase):
    def test_limit_and_window(self) -> None:
        limiter = http_hardening.SlidingWindowLimiter(2, 60)
        self.assertTrue(limiter.allow("a", now=0))
        self.assertTrue(limiter.allow("a", now=1))
        self.assertFalse(limiter.allow("a", now=2))
        self.assertTrue(limiter.allow("b", now=2))
        self.assertTrue(limiter.allow("a", now=61))

    def test_key_table_is_bounded(self) -> None:
        limiter = http_hardening.SlidingWindowLimiter(1, 60, max_keys=10)
        for index in range(50):
            limiter.allow(f"k{index}", now=0)
        self.assertLessEqual(len(limiter._events), 10)


class LoginCodeLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        oauth.login_code_limiter().reset()

    def tearDown(self) -> None:
        oauth.login_code_limiter().reset()

    def test_codes_per_email_are_limited_and_logged_without_the_email(self) -> None:
        with patch("procurement_core.oauth.send_login_code", return_value=True):
            for _ in range(oauth.LOGIN_CODES_PER_EMAIL):
                oauth.start_login("owner@shop.ca", {})
            out = io.StringIO()
            with redirect_stdout(out), self.assertRaises(oauth.OAuthError) as caught:
                oauth.start_login("Owner@Shop.ca", {})
            # A different address is not affected.
            oauth.start_login("other@shop.ca", {})
        self.assertEqual(caught.exception.status_code, 429)
        events = _events(out.getvalue(), "login_code_throttled")
        self.assertEqual(len(events), 1)
        self.assertNotIn("shop.ca", out.getvalue())


class SecurityEventTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = TestClient(app)
        self.client = self.context.__enter__()

    def tearDown(self) -> None:
        self.context.__exit__(None, None, None)

    def test_token_denial_is_logged_without_secrets(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            response = self.client.post("/token", data={
                "grant_type": "authorization_code", "code": "secret-code-value", "client_id": "abc",
                "code_verifier": "verifier-value", "redirect_uri": "http://127.0.0.1/cb",
            })
        self.assertGreaterEqual(response.status_code, 400)
        events = _events(out.getvalue(), "oauth_token_denied")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["grant_type"], "authorization_code")
        self.assertNotIn("secret-code-value", out.getvalue())
        self.assertNotIn("verifier-value", out.getvalue())

    def test_client_registration_is_logged(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            response = self.client.post("/register", json={
                "client_name": "test", "redirect_uris": ["http://127.0.0.1:33418/callback"],
                "token_endpoint_auth_method": "none",
            })
        self.assertEqual(response.status_code, 201, response.text)
        events = _events(out.getvalue(), "oauth_client_registered")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["redirect_hosts"], "127.0.0.1")
        self.assertNotIn(response.json()["client_id"], out.getvalue())


if __name__ == "__main__":
    unittest.main()
