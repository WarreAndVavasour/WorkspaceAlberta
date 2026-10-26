"""Tests for server-side PostHog telemetry: gating, payload shape, delivery."""

import json
import os
import unittest
from unittest import mock

from procurement_core import telemetry


class DisabledByDefaultTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("POSTHOG_API_KEY", None)

    def test_capture_is_a_noop_without_api_key(self) -> None:
        self.assertFalse(telemetry.enabled())
        self.assertFalse(telemetry.capture("tool_called"))

    def test_helpers_are_noops_without_api_key(self) -> None:
        self.assertFalse(telemetry.capture_tool_call("search_opportunities", "mcp", None, {}, "ok", 5))
        self.assertFalse(telemetry.capture_gate_denied("process_bid_room", "rest", 401))


class PayloadShapeTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["POSTHOG_API_KEY"] = "phc_test"
        self.payloads: list[dict] = []
        self.patcher = mock.patch.object(telemetry, "_dispatch", side_effect=lambda p: self.payloads.append(p) or True)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        os.environ.pop("POSTHOG_API_KEY", None)

    def test_tool_call_event_properties(self) -> None:
        telemetry.capture_tool_call(
            "find_matching_opportunities",
            "mcp",
            {"key_hash": "a" * 64, "plan": "pro"},
            {"profile": {"description": "steel"}},
            "# Matching Opportunities",
            123,
        )
        (payload,) = self.payloads
        self.assertEqual(payload["event"], "tool_called")
        self.assertEqual(payload["distinct_id"], "sub_" + "a" * 16)
        props = payload["properties"]
        self.assertEqual(props["tool"], "find_matching_opportunities")
        self.assertEqual(props["transport"], "mcp")
        self.assertTrue(props["authenticated"])
        self.assertEqual(props["plan"], "pro")
        self.assertTrue(props["success"])
        self.assertTrue(props["has_inline_profile"])
        self.assertEqual(props["latency_ms"], 123)
        self.assertFalse(props["$process_person_profile"])
        # Privacy: the profile contents never leave the server.
        self.assertNotIn("description", str(props))

    def test_anonymous_error_call(self) -> None:
        telemetry.capture_tool_call("search_opportunities", "rest", None, None, "Error: boom", 9)
        (payload,) = self.payloads
        self.assertEqual(payload["distinct_id"], "anonymous")
        self.assertFalse(payload["properties"]["authenticated"])
        self.assertFalse(payload["properties"]["success"])
        self.assertFalse(payload["properties"]["has_inline_profile"])

    def test_gate_denied_event(self) -> None:
        telemetry.capture_gate_denied("process_bid_room", "mcp", 401)
        (payload,) = self.payloads
        self.assertEqual(payload["event"], "pro_tool_denied")
        self.assertEqual(payload["properties"]["status_code"], 401)


class DeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["POSTHOG_API_KEY"] = "phc_test"

    def tearDown(self) -> None:
        os.environ.pop("POSTHOG_API_KEY", None)

    def test_worker_posts_queued_events(self) -> None:
        posted: list[dict] = []
        with mock.patch.object(telemetry, "_post", side_effect=posted.append):
            self.assertTrue(telemetry.capture("landing_page_viewed", properties={"source": "direct"}))
            telemetry._queue.join()
        (payload,) = posted
        self.assertEqual(payload["event"], "landing_page_viewed")
        self.assertEqual(payload["properties"]["environment"], "prod")

    def test_full_queue_drops_instead_of_blocking(self) -> None:
        with mock.patch.object(telemetry._queue, "put_nowait", side_effect=telemetry.queue.Full):
            self.assertFalse(telemetry.capture("tool_called"))


class CloudLoggingLineTest(unittest.TestCase):
    """The stdout JSON line feeds the Cloud Run log-based metrics."""

    def setUp(self) -> None:
        os.environ.pop("POSTHOG_API_KEY", None)
        os.environ.pop("WA_TOOL_LOG", None)

    def _lines(self, fn) -> list[dict]:
        import io
        import json
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            fn()
        return [json.loads(line) for line in buf.getvalue().splitlines() if line]

    def test_tool_call_line_written_without_posthog(self) -> None:
        (line,) = self._lines(lambda: telemetry.capture_tool_call(
            "search_opportunities", "mcp",
            {"user_id": "u" * 40, "plan": "pro", "pro_active": True, "email": "a@b.ca"},
            {"profile": {"description": "steel"}, "query": "bridges"},
            "# Results", 42,
        ))
        self.assertEqual(line["event"], "mcp_tool_call")
        self.assertEqual(line["tool"], "search_opportunities")
        self.assertEqual(line["user"], "user_" + "u" * 16)
        self.assertEqual(line["tier"], "pro")
        self.assertTrue(line["ok"])
        self.assertEqual(line["duration_ms"], 42)
        self.assertEqual(line["severity"], "INFO")
        # Privacy: no email, arguments or result text.
        raw = str(line)
        for secret in ("a@b.ca", "steel", "bridges", "# Results"):
            self.assertNotIn(secret, raw)

    def test_anonymous_failure_line(self) -> None:
        (line,) = self._lines(lambda: telemetry.capture_tool_call(
            "get_opportunity_details", "rest", None, None, "Error: nope", 7))
        self.assertEqual(line["user"], "anon")
        self.assertEqual(line["tier"], "anon")
        self.assertFalse(line["ok"])
        self.assertEqual(line["severity"], "WARNING")

    def test_free_tier_and_gate_denied(self) -> None:
        (line,) = self._lines(lambda: telemetry.capture_tool_call(
            "get_my_profile", "mcp", {"key_hash": "k" * 64}, {}, "ok", 1))
        self.assertEqual(line["tier"], "free")
        (denied,) = self._lines(lambda: telemetry.capture_gate_denied("process_bid_room", "mcp", 401))
        self.assertEqual(denied["event"], "mcp_gate_denied")
        self.assertEqual(denied["status_code"], 401)

    def test_can_be_disabled(self) -> None:
        os.environ["WA_TOOL_LOG"] = "0"
        try:
            self.assertEqual(self._lines(lambda: telemetry.capture_tool_call(
                "search_opportunities", "mcp", None, {}, "ok", 1)), [])
        finally:
            os.environ.pop("WA_TOOL_LOG", None)


CLOUDFLARE_PEER = "2a06:98c0:3600::103"  # Worker egress, inside 2a06:98c0::/29
VISITOR_V6 = "2001:4860:4860::8888"


class ClientIpTest(unittest.TestCase):
    """``$ip`` header selection: Cloudflare, X-Forwarded-For, none."""

    def test_cloudflare_peer_uses_cf_connecting_ip(self) -> None:
        headers = {"x-forwarded-for": f"9.9.9.9, {CLOUDFLARE_PEER}", "cf-connecting-ip": VISITOR_V6}
        self.assertEqual(telemetry.client_ip(headers), (VISITOR_V6, "cf-connecting-ip"))

    def test_cf_header_from_a_non_cloudflare_peer_is_ignored(self) -> None:
        # Anyone can send CF-Connecting-IP straight to run.app; trust only the hop.
        headers = {"x-forwarded-for": "8.8.4.4", "cf-connecting-ip": "1.1.1.1"}
        self.assertEqual(telemetry.client_ip(headers), ("8.8.4.4", "x-forwarded-for"))

    def test_right_most_forwarded_entry_wins_over_spoofed_left_entries(self) -> None:
        headers = {"x-forwarded-for": "1.2.3.4, 8.8.4.4"}
        self.assertEqual(telemetry.client_ip(headers), ("8.8.4.4", "x-forwarded-for"))

    def test_cloudflare_peer_without_visitor_or_with_worker_address_is_none(self) -> None:
        self.assertEqual(telemetry.client_ip({"x-forwarded-for": CLOUDFLARE_PEER}), ("", "none"))
        headers = {"x-forwarded-for": CLOUDFLARE_PEER, "cf-connecting-ip": CLOUDFLARE_PEER}
        self.assertEqual(telemetry.client_ip(headers), ("", "none"))

    def test_no_headers_private_peer_is_none(self) -> None:
        self.assertEqual(telemetry.client_ip({}, "127.0.0.1"), ("", "none"))
        self.assertEqual(telemetry.client_ip({}), ("", "none"))

    def test_public_socket_peer_without_forwarding(self) -> None:
        self.assertEqual(telemetry.client_ip({}, "8.8.8.8"), ("8.8.8.8", "peer"))


class CallerContextTest(unittest.TestCase):
    def test_session_id_carries_client_info_across_requests(self) -> None:
        session_id = telemetry.mint_session_id("claude-code", "2.1.0", "2025-06-18")
        self.assertTrue(session_id.isascii() and session_id.isprintable())
        first = telemetry.caller_context({"mcp-session-id": session_id}, transport="mcp")
        second = telemetry.caller_context({"mcp-session-id": session_id}, transport="mcp")
        self.assertEqual(first["client_name"], "claude-code")
        self.assertEqual(first["client_version"], "2.1.0")
        self.assertEqual(first["protocol_version"], "2025-06-18")
        self.assertEqual(first["ua_family"], "claude")
        self.assertEqual(first["mcp_session_id_hash"], second["mcp_session_id_hash"])
        self.assertEqual(len(first["mcp_session_id_hash"]), 16)
        self.assertNotIn(session_id, str(telemetry.caller_properties(first)))

    def test_forged_session_id_is_ignored(self) -> None:
        session_id = telemetry.mint_session_id("claude-code", "2.1.0", "2025-06-18")
        prefix, body, _sig = session_id.split(".")
        caller = telemetry.caller_context({"mcp-session-id": f"{prefix}.{body}.AAAA"}, transport="mcp")
        self.assertEqual(caller["client_name"], "unknown")

    def test_per_request_client_info_wins(self) -> None:
        caller = telemetry.caller_context(
            {"mcp-protocol-version": "2026-07-28"}, transport="mcp",
            client_info={"name": "Cursor", "version": "3.0"}, protocol_version="2026-07-28",
        )
        self.assertEqual((caller["client_name"], caller["client_version"]), ("Cursor", "3.0"))
        self.assertEqual(caller["ua_family"], "cursor")

    def test_rest_fallback(self) -> None:
        caller = telemetry.caller_context({"user-agent": "curl/8.5.0"}, transport="rest")
        self.assertEqual(caller["client_name"], "rest")
        self.assertEqual(caller["ua_family"], "other client")
        self.assertEqual(caller["mcp_session_id_hash"], "")
        browser = telemetry.caller_context({"user-agent": "Mozilla/5.0 (X11) Firefox/140"}, transport="rest")
        self.assertEqual(browser["ua_family"], "browser")

    def test_ua_families(self) -> None:
        cases = {
            ("Mozilla/5.0 (Macintosh) Safari/605", ""): "browser",
            ("Mozilla/5.0 (compatible; Googlebot/2.1)", ""): "bot",
            ("python-httpx/0.28", "openai-mcp"): "chatgpt",
            ("node", "Visual Studio Code"): "vscode",
            ("node", "claude-ai"): "claude",
            ("Go-http-client/2.0", ""): "other client",
        }
        for (agent, name), family in cases.items():
            self.assertEqual(telemetry.ua_family(agent, name), family, (agent, name))

    def test_user_agent_truncated(self) -> None:
        caller = telemetry.caller_context({"user-agent": "x" * 500}, transport="web")
        self.assertEqual(len(caller["user_agent"]), 200)

    def test_internal_by_client_name_user_agent_or_env(self) -> None:
        self.assertTrue(telemetry.is_internal("wv-harness", ""))
        self.assertTrue(telemetry.is_internal("", "WorkspaceAlberta-Acceptance/1.0"))
        self.assertFalse(telemetry.is_internal("claude-code", "node"))
        with mock.patch.dict(os.environ, {"WA_INTERNAL_CLIENTS": "seo-dashboard"}):
            self.assertTrue(telemetry.is_internal("seo-dashboard", ""))


class DistinctIdTest(unittest.TestCase):
    def test_rules(self) -> None:
        session = telemetry.caller_context(
            {"mcp-session-id": telemetry.mint_session_id("c", "1", "p")}, transport="mcp")
        self.assertEqual(telemetry.distinct_id_for(None, session), f"anon:{session['mcp_session_id_hash']}")
        self.assertEqual(telemetry.distinct_id_for(None, None), "anonymous")
        self.assertEqual(telemetry.distinct_id_for(None, telemetry.caller_context({}, transport="rest")), "anonymous")
        self.assertEqual(telemetry.distinct_id_for({"key_hash": "b" * 64}, session), "sub_" + "b" * 16)
        self.assertEqual(telemetry.distinct_id_for({"user_id": "acct_123"}, session), "user_acct_123")

    def test_email_account_id_is_hashed(self) -> None:
        distinct = telemetry.distinct_id_for({"user_id": "Owner@Example.ca"}, None)
        self.assertTrue(distinct.startswith("user_"))
        self.assertNotIn("@", distinct)
        self.assertNotIn("example", distinct.lower())


class CallerOnEventsTest(PayloadShapeTest):
    """Caller properties land on every request event."""

    def test_tool_call_and_denied_carry_caller(self) -> None:
        session_id = telemetry.mint_session_id("claude-code", "2.1.0", "2025-06-18")
        caller = telemetry.caller_context(
            {"mcp-session-id": session_id, "x-forwarded-for": "8.8.4.4", "user-agent": "claude-code/2.1.0"},
            transport="mcp",
        )
        telemetry.capture_tool_call("search_opportunities", "mcp", None, {}, "ok", 3, caller=caller)
        telemetry.capture_gate_denied("process_bid_room", "mcp", 401, caller=caller)
        for payload in self.payloads:
            props = payload["properties"]
            self.assertEqual(props["client_name"], "claude-code")
            self.assertEqual(props["client_version"], "2.1.0")
            self.assertEqual(props["protocol_version"], "2025-06-18")
            self.assertEqual(props["$ip"], "8.8.4.4")
            self.assertFalse(props["is_internal"])
            self.assertEqual(payload["distinct_id"], f"anon:{caller['mcp_session_id_hash']}")
            self.assertFalse(props["$process_person_profile"])

    def test_no_address_disables_geoip(self) -> None:
        telemetry.capture("tool_called", caller=telemetry.caller_context({}, transport="rest"))
        props = self.payloads[0]["properties"]
        self.assertNotIn("$ip", props)
        self.assertTrue(props["$geoip_disable"])


class HttpCallerTest(unittest.TestCase):
    """End to end through the ASGI app: session header, landing split."""

    @classmethod
    def setUpClass(cls) -> None:
        import sys
        import tempfile
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.setdefault("CANADABUYS_DATA_DIR", cls.tmp.name)
        os.environ.setdefault("WA_OAUTH_STORE", "memory")
        os.environ.setdefault("WA_OAUTH_SIGNING_KEY", "test-oauth-signing-key")
        sys.path.insert(0, str(root / "mcp-servers" / "canadabuys"))
        from fastapi.testclient import TestClient
        import server_http
        cls.context = TestClient(server_http.app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.context.__exit__(None, None, None)
        cls.tmp.cleanup()

    def setUp(self) -> None:
        os.environ["POSTHOG_API_KEY"] = "phc_test"
        self.payloads: list[dict] = []
        self.patcher = mock.patch.object(telemetry, "_dispatch", side_effect=lambda p: self.payloads.append(p) or True)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        os.environ.pop("POSTHOG_API_KEY", None)

    def _rpc(self, body: dict, session_id: str | None = None):
        headers = {"Accept": "application/json", "User-Agent": "claude-code/2.1.0"}
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return self.client.post("/mcp", headers=headers, json=body)

    def test_client_info_propagates_across_the_session(self) -> None:
        init = self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "claude-code", "version": "2.1.0"},
        }})
        self.assertEqual(init.status_code, 200)
        session_id = init.headers["mcp-session-id"]
        call = self._rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": "get_server_guide", "arguments": {}}}, session_id)
        self.assertEqual(call.status_code, 200)
        (event,) = [p for p in self.payloads if p["event"] == "tool_called"]
        props = event["properties"]
        self.assertEqual((props["client_name"], props["client_version"]), ("claude-code", "2.1.0"))
        self.assertEqual(props["protocol_version"], "2025-06-18")
        self.assertEqual(props["mcp_session_id_hash"], telemetry.session_hash(session_id))
        self.assertTrue(event["distinct_id"].startswith("anon:"))
        self.assertNotIn(session_id, json.dumps(event))

    def test_landing_for_browsers_endpoint_root_for_everything_else(self) -> None:
        self.client.get("/", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/141"})
        self.client.get("/", headers={"User-Agent": "claude-code/2.1.0"})
        browser, client = self.payloads
        self.assertEqual(browser["event"], "landing_page_viewed")
        self.assertTrue(browser["properties"]["is_browser"])
        self.assertEqual(browser["properties"]["ua_family"], "browser")
        self.assertEqual(client["event"], "endpoint_root_hit")
        self.assertFalse(client["properties"]["is_browser"])
        self.assertEqual(client["properties"]["ua_family"], "claude")
        self.assertEqual(client["properties"]["user_agent"], "claude-code/2.1.0")


if __name__ == "__main__":
    unittest.main()
