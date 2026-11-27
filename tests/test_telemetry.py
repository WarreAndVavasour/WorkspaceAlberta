"""Tests for server-side PostHog telemetry: gating, payload shape, delivery."""

import json
import os
import unittest
from unittest import mock

from procurement_core import telemetry


class DisabledByDefaultTest(unittest.TestCase):
    def setUp(self) -> None:
        for key in ("POSTHOG_API_KEY", "POSTHOG_PROJECT_TOKEN", "POSTHOG_PROJECT_KEY"):
            os.environ.pop(key, None)

    def test_capture_is_a_noop_without_api_key(self) -> None:
        self.assertFalse(telemetry.enabled())
        self.assertFalse(telemetry.capture("tool_called"))

    def test_personal_api_key_is_ignored_unless_project_token_is_present(self) -> None:
        with mock.patch.dict(os.environ, {"POSTHOG_API_KEY": "phx_personal_secret"}, clear=False):
            self.assertEqual(telemetry.api_key(), "")
            self.assertFalse(telemetry.enabled())
        with mock.patch.dict(
            os.environ,
            {"POSTHOG_API_KEY": "phx_personal_secret", "POSTHOG_PROJECT_TOKEN": "phc_project_token"},
            clear=False,
        ):
            self.assertEqual(telemetry.api_key(), "phc_project_token")
            self.assertTrue(telemetry.enabled())

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
        call = self._rpc(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_server_guide",
                    "arguments": {
                        "context": "Checking procurement server capabilities for a welding shop",
                        "llm_model": "claude-sonnet-4-6",
                    },
                },
            },
            session_id,
        )
        self.assertEqual(call.status_code, 200)
        self.assertFalse(call.json()["result"].get("isError"))
        # Legacy custom event is gone on /mcp; PostHog MCP Analytics reads $mcp_tool_call.
        self.assertEqual([p for p in self.payloads if p["event"] == "tool_called"], [])
        (init_event,) = [p for p in self.payloads if p["event"] == "$mcp_initialize"]
        (event,) = [p for p in self.payloads if p["event"] == "$mcp_tool_call"]
        props = event["properties"]
        self.assertEqual(props["$mcp_source"], "posthog_mcp_analytics")
        self.assertEqual(props["$mcp_tool_name"], "get_server_guide")
        self.assertEqual((props["$mcp_client_name"], props["$mcp_client_version"]), ("claude-code", "2.1.0"))
        self.assertEqual((props["client_name"], props["client_version"]), ("claude-code", "2.1.0"))
        self.assertEqual(props["protocol_version"], "2025-06-18")
        self.assertEqual(props["mcp_session_id_hash"], telemetry.session_hash(session_id))
        self.assertEqual(props["$session_id"], init_event["properties"]["$session_id"])
        self.assertTrue(props["$session_id"].startswith("ses_"))
        self.assertEqual(event["distinct_id"], props["$session_id"])
        self.assertEqual(props["$mcp_intent"], "Checking procurement server capabilities for a welding shop")
        self.assertEqual(props["$mcp_intent_source"], "context_parameter")
        self.assertEqual(props["$mcp_llm_model"], "claude-sonnet-4-6")
        self.assertFalse(props["$process_person_profile"])
        self.assertNotIn("$mcp_parameters", props)
        self.assertNotIn("$mcp_response", props)
        self.assertNotIn(session_id, json.dumps(event))

    def test_privacy_strips_inline_profile_while_keeping_input_keys_and_inferred_intent(self) -> None:
        call = self._rpc({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "list_deadlines",
                "arguments": {"days": 7, "source": "alberta"},
            },
        })
        self.assertEqual(call.status_code, 200)
        (event,) = [p for p in self.payloads if p["event"] == "$mcp_tool_call"]
        props = event["properties"]
        self.assertEqual(props["$mcp_tool_name"], "list_deadlines")
        self.assertEqual(props["$mcp_intent_source"], "inferred")
        self.assertIn("source=alberta", props["$mcp_intent"])
        self.assertIn("days=7", props["$mcp_intent"])
        self.assertEqual(sorted(props["$mcp_input_keys"]), ["days", "source"])
        self.assertNotIn("$mcp_parameters", props)
        self.assertNotIn("$mcp_response", props)

    def test_virtual_feedback_and_missing_capability_tools_are_listed_and_emit_events(self) -> None:
        import io
        from contextlib import redirect_stdout

        listing = self._rpc({"jsonrpc": "2.0", "id": 11, "method": "tools/list"})
        self.assertEqual(listing.status_code, 200)
        tools = {t["name"]: t for t in listing.json()["result"]["tools"]}
        self.assertIn("send_feedback", tools)
        self.assertIn("get_more_tools", tools)
        for vname in ("send_feedback", "get_more_tools"):
            self.assertIn({"type": "noauth"}, tools[vname]["securitySchemes"])
            self.assertEqual(tools[vname]["securitySchemes"], tools[vname]["_meta"]["securitySchemes"])

        missing = self._rpc({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "get_more_tools",
                "arguments": {"context": "Need a tool to export tender deadlines to CSV"},
            },
        })
        self.assertEqual(missing.status_code, 200)
        self.assertFalse(missing.json()["result"].get("isError"))
        (missing_ev,) = [p for p in self.payloads if p["event"] == "$mcp_missing_capability"]
        self.assertEqual(missing_ev["properties"]["$mcp_intent"], "Need a tool to export tender deadlines to CSV")

        buf = io.StringIO()
        with redirect_stdout(buf):
            fb = self._rpc({
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "send_feedback",
                    "arguments": {
                        "feedback_type": "missing_capability",
                        "summary": "No municipal tender feed for Calgary yet",
                        "details": "Tried searching City of Calgary tenders directly",
                        "sentiment": "neutral",
                    },
                },
            })
        self.assertEqual(fb.status_code, 200)
        self.assertFalse(fb.json()["result"].get("isError"))
        (fb_ev,) = [p for p in self.payloads if p["event"] == "$mcp_feedback"]
        self.assertEqual(fb_ev["properties"]["$mcp_feedback_type"], "missing_capability")
        self.assertIn("Calgary", fb_ev["properties"]["$mcp_feedback_summary"])
        cloud_logs = [json.loads(line) for line in buf.getvalue().splitlines() if line.startswith("{")]
        self.assertTrue(any(entry.get("event") == "mcp_feedback" for entry in cloud_logs))

    def test_errors_and_unknown_tools_record_failures_and_exceptions(self) -> None:
        unknown = self._rpc({
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "nonexistent_probe_tool", "arguments": {}},
        })
        self.assertEqual(unknown.status_code, 200)
        self.assertTrue(unknown.json()["result"]["isError"])
        (call_ev,) = [p for p in self.payloads if p["event"] == "$mcp_tool_call"]
        (exc_ev,) = [p for p in self.payloads if p["event"] == "$exception"]
        self.assertTrue(call_ev["properties"]["$mcp_is_error"])
        self.assertEqual(call_ev["properties"]["$mcp_error_type"], "unknown_tool")
        self.assertIn("Unknown tool", call_ev["properties"]["$mcp_error_message"])
        self.assertEqual(exc_ev["properties"]["$mcp_tool_name"], "nonexistent_probe_tool")

        self.payloads.clear()
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}), mock.patch(
            "server_http.check_tool_access", return_value={"user_id": "acct_999", "plan": "pro", "pro_active": True}
        ):
            failed = self._rpc({
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {"name": "classify_tender", "arguments": {"reference": "AB-2026-06584"}},
            })
        self.assertEqual(failed.status_code, 200)
        self.assertTrue(failed.json()["result"]["isError"])
        (fail_ev,) = [p for p in self.payloads if p["event"] == "$mcp_tool_call"]
        (fail_exc,) = [p for p in self.payloads if p["event"] == "$exception"]
        self.assertTrue(fail_ev["properties"]["$mcp_is_error"])
        self.assertEqual(fail_ev["distinct_id"], "user_acct_999")
        self.assertEqual(fail_ev["properties"]["reference"], "AB-2026-06584")
        self.assertIn("not configured", fail_ev["properties"]["$mcp_error_message"])
        self.assertEqual(fail_exc["properties"]["$mcp_tool_name"], "classify_tender")

    def test_gate_denials_and_submit_feedback_mirror_into_posthog_mcp(self) -> None:
        from procurement_core.auth import GateError

        # 402 inside handle_call_tool records both pro_tool_denied and $mcp_tool_call permission error.
        with mock.patch("server_http.check_tool_access", side_effect=GateError(402, "Subscription inactive")):
            denied = self._rpc({
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {"name": "process_bid_room", "arguments": {"reference": "AB-2026-00001"}},
            })
        self.assertEqual(denied.status_code, 200)
        self.assertTrue(denied.json()["result"]["isError"])
        (gate_ev,) = [p for p in self.payloads if p["event"] == "pro_tool_denied"]
        (mcp_err,) = [p for p in self.payloads if p["event"] == "$mcp_tool_call"]
        self.assertEqual(gate_ev["properties"]["status_code"], 402)
        self.assertTrue(mcp_err["properties"]["$mcp_is_error"])
        self.assertEqual(mcp_err["properties"]["$mcp_error_type"], "permission")
        self.assertEqual(mcp_err["properties"]["$mcp_error_status"], 402)

        # HTTP-layer 401 challenge on anonymous protected tool call also emits pro_tool_denied.
        self.payloads.clear()
        with mock.patch.dict(os.environ, {"WA_HOSTED": "1"}):
            unauth = self._rpc({
                "jsonrpc": "2.0",
                "id": 31,
                "method": "tools/call",
                "params": {"name": "get_my_profile", "arguments": {}},
            })
        self.assertEqual(unauth.status_code, 401)
        (challenge_ev,) = [p for p in self.payloads if p["event"] == "pro_tool_denied"]
        self.assertEqual(challenge_ev["properties"]["tool"], "get_my_profile")
        self.assertEqual(challenge_ev["properties"]["status_code"], 401)

        # Calling WorkspaceAlberta's submit_feedback tool over MCP also emits $mcp_feedback.
        self.payloads.clear()
        init = self._rpc({
            "jsonrpc": "2.0",
            "id": 32,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "cursor", "version": "1.2.0"},
            },
        })
        sid = init.headers["mcp-session-id"]
        sub_fb = self._rpc(
            {
                "jsonrpc": "2.0",
                "id": 33,
                "method": "tools/call",
                "params": {
                    "name": "submit_feedback",
                    "arguments": {
                        "category": "missing_capability",
                        "summary": "Need Saskatchewan SaskTenders coverage",
                        "what_i_was_trying_to_do": "Search provincial steel tenders across both Alberta and Saskatchewan.",
                        "what_went_wrong": "Only federal CanadaBuys and Alberta APC notices are indexed right now.",
                    },
                },
            },
            sid,
        )
        self.assertEqual(sub_fb.status_code, 200)
        self.assertFalse(sub_fb.json()["result"].get("isError"))
        (mirrored_fb,) = [p for p in self.payloads if p["event"] == "$mcp_feedback"]
        self.assertEqual(mirrored_fb["properties"]["$mcp_feedback_type"], "missing_capability")
        self.assertIn("SaskTenders", mirrored_fb["properties"]["$mcp_feedback_summary"])
        self.assertTrue(mirrored_fb["properties"]["$session_id"].startswith("ses_"))

    def test_posthog_project_token_alias_enables_telemetry(self) -> None:
        with mock.patch.dict(os.environ, {"POSTHOG_API_KEY": "", "POSTHOG_PROJECT_TOKEN": "phc_alias"}, clear=False):
            self.assertEqual(telemetry.api_key(), "phc_alias")
            self.assertTrue(telemetry.enabled())

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
