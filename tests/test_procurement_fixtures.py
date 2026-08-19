"""Offline fixture ingest for CanadaBuys and Alberta Purchasing Connection.

A shop-in-Red-Deer query must return structured tender rows from both
fixture sources (title, close date, source) without any network access.
The stdio smoke test stays separate: ``python -m unittest tests.test_canadabuys_mcp_smoke``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "procurement"
sys.path.insert(0, str(ROOT))

# Keep imports side-effect free (service.py creates DATA_DIR at import time).
os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="canadabuys-test-"))

from procurement_core import fixtures, service  # noqa: E402


SHOP_QUERY = "welding shop Red Deer"
FEDERAL_TITLE = "Mobile Welding Shop Services - Red Deer, Alberta"
APC_TITLE = "CWB Welding Shop Fit-Up - City of Red Deer"
FEDERAL_CLOSING = "2026-09-15T14:00:00"
APC_CLOSING = "2026-09-22T16:00:00Z"
HOSPITALITY_MARKERS = ("Catering", "Banquet", "Hotel Catering")


class ProcurementFixtureIngestTest(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_fixture_dir = os.environ.get(fixtures.FIXTURE_DIR_ENV)
        os.environ[fixtures.FIXTURE_DIR_ENV] = str(FIXTURE_DIR)

    def tearDown(self) -> None:
        if self._previous_fixture_dir is None:
            os.environ.pop(fixtures.FIXTURE_DIR_ENV, None)
        else:
            os.environ[fixtures.FIXTURE_DIR_ENV] = self._previous_fixture_dir

    def test_fixture_files_parse_as_source_shapes(self) -> None:
        rows = fixtures.load_canadabuys_rows()
        payload = fixtures.load_apc_search_payload()
        self.assertIsNotNone(rows)
        self.assertIsNotNone(payload)
        assert rows is not None
        assert payload is not None
        self.assertGreaterEqual(len(rows), 2)
        self.assertIn("title-titre-eng", rows[0])
        self.assertIn("tenderClosingDate-appelOffresDateCloture", rows[0])
        self.assertIn("values", payload)
        self.assertEqual(payload["values"][0]["referenceNumber"], "AB-2026-04112")

    def test_shop_in_red_deer_query_returns_structured_rows_from_both_sources(self) -> None:
        with mock.patch.object(service, "urlopen", side_effect=AssertionError("network")):
            opportunities, warnings = service.collect_unified_search(
                {"keywords": SHOP_QUERY, "source": "all", "limit": 20}
            )

        self.assertEqual(warnings, [])
        self.assertGreaterEqual(len(opportunities), 2)

        by_source = {row["source"]: row for row in opportunities}
        self.assertIn("CanadaBuys", by_source)
        self.assertIn("Alberta Purchasing Connection", by_source)

        federal = by_source["CanadaBuys"]
        alberta = by_source["Alberta Purchasing Connection"]
        self.assertEqual(federal["title"], FEDERAL_TITLE)
        self.assertEqual(federal["closing"], FEDERAL_CLOSING)
        self.assertEqual(federal["source"], "CanadaBuys")
        self.assertEqual(alberta["title"], APC_TITLE)
        self.assertEqual(alberta["closing"], APC_CLOSING)
        self.assertEqual(alberta["source"], "Alberta Purchasing Connection")

        titles = [row["title"] for row in opportunities]
        for marker in HOSPITALITY_MARKERS:
            self.assertFalse(any(marker in title for title in titles))

        for row in opportunities:
            self.assertTrue(str(row.get("title") or "").strip())
            self.assertTrue(str(row.get("closing") or "").strip())
            self.assertTrue(str(row.get("source") or "").strip())

    def test_source_filters_keep_fixture_ingest_separate(self) -> None:
        with mock.patch.object(service, "urlopen", side_effect=AssertionError("network")):
            federal, federal_warnings = service.collect_unified_search(
                {"keywords": SHOP_QUERY, "source": "federal"}
            )
            alberta, alberta_warnings = service.collect_unified_search(
                {"keywords": SHOP_QUERY, "source": "alberta"}
            )

        self.assertEqual(federal_warnings, [])
        self.assertEqual(alberta_warnings, [])
        self.assertEqual({row["source"] for row in federal}, {"CanadaBuys"})
        self.assertEqual({row["source"] for row in alberta}, {"Alberta Purchasing Connection"})
        self.assertEqual(federal[0]["title"], FEDERAL_TITLE)
        self.assertEqual(alberta[0]["title"], APC_TITLE)

    def test_search_opportunities_markdown_includes_title_close_date_and_source(self) -> None:
        with mock.patch.object(service, "urlopen", side_effect=AssertionError("network")):
            output = asyncio.run(service.search_opportunities({"keywords": SHOP_QUERY}))

        self.assertIn(FEDERAL_TITLE, output)
        self.assertIn(APC_TITLE, output)
        self.assertIn("Source: CanadaBuys", output)
        self.assertIn("Source: Alberta Purchasing Connection", output)
        self.assertIn(f"Closing: {FEDERAL_CLOSING}", output)
        self.assertIn(f"Closing: {APC_CLOSING}", output)
        self.assertNotIn("CanadaBuys data unavailable", output)
        self.assertNotIn("Alberta APC unavailable", output)

    def test_structured_output_carries_normalized_opportunities(self) -> None:
        with mock.patch.object(service, "urlopen", side_effect=AssertionError("network")):
            text, structured = asyncio.run(
                service.call_tool_text_and_structured("search_opportunities", {"keywords": SHOP_QUERY})
            )

        self.assertIn(FEDERAL_TITLE, text)
        self.assertIn(APC_TITLE, text)
        self.assertIsNotNone(structured)
        assert structured is not None
        self.assertEqual(structured["kind"], "opportunities")
        self.assertEqual(structured["count"], len(structured["opportunities"]))
        titles = {row["title"] for row in structured["opportunities"]}
        self.assertIn(FEDERAL_TITLE, titles)
        self.assertIn(APC_TITLE, titles)
        sources = {row["source"] for row in structured["opportunities"]}
        self.assertIn("CanadaBuys", sources)
        self.assertIn("Alberta Purchasing Connection", sources)
        for row in structured["opportunities"]:
            self.assertIn("reference", row)
            self.assertIn("closing", row)

    def test_matches_structured_output_has_score_and_reasons_shape(self) -> None:
        with mock.patch.object(service, "urlopen", side_effect=AssertionError("network")):
            text, structured = asyncio.run(
                service.call_tool_text_and_structured(
                    "find_matching_opportunities",
                    {
                        "profile": {
                            "company_name": "Red Deer Welding",
                            "location": "Red Deer, Alberta",
                            "description": "structural steel fabrication and welding",
                        }
                    },
                )
            )

        self.assertIsNotNone(structured)
        assert structured is not None
        self.assertEqual(structured["kind"], "matches")
        self.assertEqual(structured["count"], len(structured["matches"]))
        for match in structured["matches"]:
            self.assertIn("score", match)
            self.assertIn("days_until", match)
            self.assertIn("reasons", match)
            self.assertIn("reference", match)


if __name__ == "__main__":
    unittest.main()
