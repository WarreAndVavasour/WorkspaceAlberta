"""Per-tool-call metering of paid upstream APIs (procurement_core.usage)."""

import io
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from procurement_core import telemetry, usage
from procurement_core.requirements import jev


class _Response:
    def __init__(self, body: dict) -> None:
        self._raw = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


class MeterTest(unittest.TestCase):
    def test_record_without_meter_is_a_noop(self) -> None:
        self.assertIsNone(usage.current())
        usage.record("typesafe", requests=1)  # must not raise

    def test_counts_accumulate_and_cost_is_estimated(self) -> None:
        with usage.metering() as meter:
            usage.record("typesafe", requests=1, input_tokens=600_000)
            usage.record("typesafe", requests=1, input_tokens=400_000)
            usage.record("cohere", requests=1, input_tokens=10, output_tokens=0)
        fields = meter.log_fields()
        self.assertEqual(fields["upstream"]["typesafe"], {"requests": 2, "input_tokens": 1_000_000})
        self.assertEqual(fields["upstream"]["cohere"], {"requests": 1, "input_tokens": 10})
        self.assertAlmostEqual(fields["typesafe_est_usd"], usage.TYPESAFE_USD_PER_MTOK)
        self.assertIsNone(usage.current())

    def test_no_usage_means_no_fields(self) -> None:
        with usage.metering() as meter:
            pass
        self.assertEqual(meter.log_fields(), {})

    def test_bind_carries_the_meter_into_executor_threads(self) -> None:
        with usage.metering() as meter:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for future in [pool.submit(usage.bind(usage.record), "typesafe", requests=1) for _ in range(50)]:
                    future.result()
        self.assertEqual(meter.snapshot()["typesafe"]["requests"], 50)

    def test_typesafe_price_matches_the_classifier(self) -> None:
        self.assertEqual(usage.TYPESAFE_USD_PER_MTOK, jev.PRICE_PER_MTOK)


class JevClientTest(unittest.TestCase):
    def test_call_jev_records_requests_and_input_tokens(self) -> None:
        body = {"model": "jev-1.13.0", "answers": {}, "usage": {"input_tokens": 1234, "output_tokens": 20}}
        with mock.patch.object(jev, "urlopen", return_value=_Response(body)):
            with usage.metering() as meter:
                result, error, attempts = jev.call_jev({"state": {}}, "k", max_retries=0)
        self.assertEqual((error, attempts), ("", 1))
        self.assertEqual(meter.snapshot()["typesafe"], {"requests": 1, "input_tokens": 1234})


class ToolCallLineTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("POSTHOG_API_KEY", None)

    def _line(self, **kwargs) -> dict:
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            telemetry.capture_tool_call(**kwargs)
        (line,) = [json.loads(x) for x in buf.getvalue().splitlines() if x]
        return line

    def test_upstream_and_reference_on_the_log_line(self) -> None:
        line = self._line(
            tool="classify_tender", transport="mcp", record=None,
            arguments={"reference": "AB-2026-01234", "notes": "private text"},
            result_text="# Requirements", latency_ms=79528,
            upstream={"upstream": {"typesafe": {"requests": 5712, "input_tokens": 7_800_000}},
                      "typesafe_est_usd": 0.3276},
        )
        self.assertEqual(line["reference"], "AB-2026-01234")
        self.assertEqual(line["upstream"]["typesafe"]["requests"], 5712)
        self.assertEqual(line["typesafe_est_usd"], 0.3276)
        self.assertNotIn("private text", json.dumps(line))

    def test_line_unchanged_when_nothing_metered(self) -> None:
        line = self._line(tool="get_server_guide", transport="mcp", record=None,
                          arguments={}, result_text="ok", latency_ms=1)
        self.assertNotIn("upstream", line)
        self.assertNotIn("reference", line)


if __name__ == "__main__":
    unittest.main()
