"""Offline tests for opera_core auth and GraphQL client.

All HTTP is stubbed by monkeypatching ``urlopen`` in the module under test;
no network access is required.

Run: python -m unittest tests.test_opera_client
"""

from __future__ import annotations

import base64
import io
import json
import unittest
from typing import Any
from urllib.parse import parse_qs

from opera_core import auth as auth_module
from opera_core import client as client_module
from opera_core.auth import AuthError, TokenManager
from opera_core.client import (
    MOCK_SAMPLE_DATA,
    GraphQLClient,
    MockGraphQLClient,
    OperaAPIError,
)
from opera_core.config import Settings


def make_settings(**overrides: Any) -> Settings:
    base = dict(
        base_url="https://opera.example.com",
        app_key="app-key-123",
        client_id="cid",
        client_secret="csecret",
        hotel_id="SAND01",
        username="integration_user",
        password="s3cret",
        grant_type="password",
    )
    base.update(overrides)
    return Settings(**base)


class FakeResponse:
    """Minimal stand-in for an urlopen response."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class TokenRequestShapeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[Any] = []
        self.original_urlopen = auth_module.urlopen

        def fake_urlopen(request: Any, timeout: int = 0) -> FakeResponse:
            self.requests.append(request)
            return FakeResponse(
                {"access_token": "tok-abc", "expires_in": 3600, "token_type": "Bearer"}
            )

        auth_module.urlopen = fake_urlopen
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        auth_module.urlopen = self.original_urlopen

    def test_password_grant_request_shape(self) -> None:
        tm = TokenManager(make_settings())
        token = tm.token()

        self.assertEqual(token, "tok-abc")
        self.assertEqual(len(self.requests), 1)
        req = self.requests[0]

        self.assertEqual(req.full_url, "https://opera.example.com/oauth/v1/tokens")
        self.assertEqual(req.get_method(), "POST")

        expected_basic = base64.b64encode(b"cid:csecret").decode()
        self.assertEqual(req.get_header("Authorization"), f"Basic {expected_basic}")
        self.assertEqual(req.get_header("X-app-key"), "app-key-123")
        self.assertEqual(
            req.get_header("Content-type"), "application/x-www-form-urlencoded"
        )

        form = parse_qs(req.data.decode())
        self.assertEqual(form["grant_type"], ["password"])
        self.assertEqual(form["username"], ["integration_user"])
        self.assertEqual(form["password"], ["s3cret"])
        self.assertNotIn("scope", form)

    def test_client_credentials_grant_includes_scope(self) -> None:
        tm = TokenManager(make_settings(grant_type="client_credentials"))
        tm.token()

        form = parse_qs(self.requests[0].data.decode())
        self.assertEqual(form["grant_type"], ["client_credentials"])
        self.assertIn("scope", form)
        self.assertNotIn("username", form)

    def test_missing_credentials_raises_auth_error(self) -> None:
        tm = TokenManager(make_settings(client_secret=""))
        with self.assertRaises(AuthError):
            tm.token()


class TokenCachingTest(unittest.TestCase):
    def test_token_cached_until_expiry_minus_skew(self) -> None:
        calls: list[Any] = []
        now = [1_000_000.0]

        def fake_urlopen(request: Any, timeout: int = 0) -> FakeResponse:
            calls.append(request)
            return FakeResponse({"access_token": f"tok-{len(calls)}", "expires_in": 3600})

        original_urlopen = auth_module.urlopen
        original_time = auth_module.time.time
        auth_module.urlopen = fake_urlopen
        auth_module.time.time = lambda: now[0]
        self.addCleanup(setattr, auth_module, "urlopen", original_urlopen)
        self.addCleanup(setattr, auth_module.time, "time", original_time)

        tm = TokenManager(make_settings())
        self.assertEqual(tm.token(), "tok-1")
        self.assertEqual(tm.token(), "tok-1")  # cached, no second fetch
        self.assertEqual(len(calls), 1)

        now[0] += 3600 - auth_module.EXPIRY_SKEW_SECONDS + 1  # inside skew window
        self.assertEqual(tm.token(), "tok-2")  # refreshed
        self.assertEqual(len(calls), 2)


class GraphQLClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[Any] = []
        self.original_urlopen = client_module.urlopen
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        client_module.urlopen = self.original_urlopen

    def _install(self, payload: dict[str, Any]) -> None:
        def fake_urlopen(request: Any, timeout: int = 0) -> FakeResponse:
            self.requests.append(request)
            return FakeResponse(payload)

        client_module.urlopen = fake_urlopen

    def _client(self) -> GraphQLClient:
        tm = TokenManager(make_settings())
        tm._access_token = "tok-abc"  # seeded: no token HTTP call needed
        tm._expires_at = float("inf")
        return GraphQLClient(make_settings(), tm)

    def test_execute_sends_headers_and_returns_data(self) -> None:
        self._install({"data": {"hotel": {"code": "SAND01"}}})
        client = self._client()

        data = client.execute("query { hotel { code } }", {"limit": 1})

        self.assertEqual(data, {"hotel": {"code": "SAND01"}})
        req = self.requests[0]
        self.assertEqual(req.full_url, "https://opera.example.com/rna/v1/graphql")
        self.assertEqual(req.get_header("Authorization"), "Bearer tok-abc")
        self.assertEqual(req.get_header("X-app-key"), "app-key-123")
        self.assertEqual(req.get_header("X-hotelid"), "SAND01")
        body = json.loads(req.data.decode())
        self.assertEqual(body["query"], "query { hotel { code } }")
        self.assertEqual(body["variables"], {"limit": 1})

    def test_graphql_errors_array_raises_opera_api_error(self) -> None:
        self._install(
            {"errors": [{"message": "bad field 'hotl'"}, {"message": "syntax error"}]}
        )
        client = self._client()

        with self.assertRaises(OperaAPIError) as ctx:
            client.execute("query { hotl }")

        self.assertIn("bad field 'hotl'", ctx.exception.message)
        self.assertIn("syntax error", ctx.exception.message)
        self.assertEqual(ctx.exception.status, 0)


class MockGraphQLClientTest(unittest.TestCase):
    def test_mock_client_returns_canned_data(self) -> None:
        client = MockGraphQLClient(make_settings())
        data = client.execute("query { hotel { code name businessDate } }")
        self.assertEqual(data, MOCK_SAMPLE_DATA)

    def test_mock_client_needs_no_credentials(self) -> None:
        client = MockGraphQLClient(Settings())
        data = client.execute("anything")
        self.assertIn("hotel", data)


if __name__ == "__main__":
    unittest.main()
