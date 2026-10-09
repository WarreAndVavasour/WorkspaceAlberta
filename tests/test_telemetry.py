"""Tests for server-side PostHog telemetry: gating, payload shape, delivery."""

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


if __name__ == "__main__":
    unittest.main()
