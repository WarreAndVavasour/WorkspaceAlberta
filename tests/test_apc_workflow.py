"""Offline integration coverage for planned retrieval and harness-facing results."""

import asyncio
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import unittest
from unittest import mock

from procurement_core import fixtures, query_planner, service


def row(reference="AB-2026-05716", title="Data platform engineering", days=10):
    return {
        "referenceNumber": reference, "title": title,
        "projectDescription": title, "commodityCodes": ["81111500"],
        "statusCode": "OPEN", "categoryCode": "SRV", "regionOfDelivery": ["Alberta"],
        "closeDateTime": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        "postDateTime": "2026-09-20T12:00:00Z",
    }


PLAN = {"source": "cohere", "unspsc": ["81000000"], "categories": ["SRV"],
        "keywords": ["data platform"], "regions": ["Calgary"]}
PROFILE = {"description": "data platform engineering", "capabilities": ["data platform engineering"],
           "location": "Alberta"}


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(fixtures, "fixture_dir", return_value=None))
        self.stack.enter_context(mock.patch.object(query_planner, "cohere_api_key", return_value="test"))
        self.planner = self.stack.enter_context(mock.patch.object(query_planner, "plan_query", return_value=PLAN))

    def test_search_uses_native_codes_preserves_explicit_category_and_status(self):
        def search(**kwargs):
            if kwargs["limit"] == 1:
                return {"facets": {"CommodityCodes": [{"value": "81000000", "count": 2}]}}
            self.assertEqual(kwargs["unspsc"], ["81000000"])
            self.assertEqual(kwargs["category"], "GD")
            self.assertEqual(kwargs["status"], "CLOSED")
            self.assertEqual(kwargs["query"], "")
            self.assertLessEqual(kwargs["timeout"], 5)
            return {"values": [row()], "totalCount": 1}
        with mock.patch.object(service, "search_alberta_api", side_effect=search):
            rows, warnings = service.collect_alberta_candidates("we build platforms", category="GD", status="CLOSED")
        self.assertEqual(len(rows), 1)
        self.assertEqual(warnings, [])
        self.planner.assert_called_once()

    def test_failed_planning_keeps_keyword_query_and_surfaces_warning(self):
        self.planner.return_value = query_planner._fallback("data platform", "request-failed")
        with mock.patch.object(service, "search_alberta_api", return_value={"facets": {}}), \
             mock.patch.object(service, "fetch_all_alberta_opportunities", return_value=([row()], "")) as fetch:
            rows, warnings = service.collect_alberta_candidates("data platform", category="GD")
        self.assertEqual(fetch.call_args.kwargs["query"], "data platform")
        self.assertEqual(fetch.call_args.kwargs["category"], "GD")
        self.assertIsNone(fetch.call_args.kwargs["unspsc"])
        self.assertTrue(any("request-failed" in warning for warning in warnings))

    def test_empty_inferred_filter_retries_with_explicit_filters(self):
        with mock.patch.object(service, "search_alberta_api", return_value={"facets": {}}), \
             mock.patch.object(service, "fetch_all_alberta_opportunities", side_effect=[([], ""), ([row()], "")]) as fetch:
            rows, warnings = service.collect_alberta_candidates("data platform", category="GD")
        self.assertEqual(len(rows), 1)
        self.assertEqual(fetch.call_args.kwargs["category"], "GD")
        self.assertNotIn("unspsc", fetch.call_args.kwargs)
        self.assertTrue(any("retrying" in warning for warning in warnings))

    def test_missing_key_skips_facets_and_uses_full_corpus_for_profiles(self):
        self.planner.return_value = query_planner._fallback("data platform", "no-api-key")
        with mock.patch.object(query_planner, "cohere_api_key", return_value=None), \
             mock.patch.object(service, "search_alberta_api") as search, \
             mock.patch.object(service, "fetch_all_alberta_opportunities", return_value=([row()], "")) as fetch:
            service.collect_alberta_candidates("data platform", profile_search=True)
        search.assert_not_called()
        self.assertEqual(fetch.call_args.kwargs["query"], "")


class PagingTests(unittest.TestCase):
    def test_page_failure_retains_rows_and_warns(self):
        with mock.patch.object(service, "search_alberta_api", side_effect=[
            {"values": [row()], "totalCount": 2}, RuntimeError("upstream")]):
            rows, warning = service.fetch_all_alberta_opportunities(page_size=1)
        self.assertEqual(len(rows), 1)
        self.assertIn("page request failed", warning)

    def test_repeated_page_stops_and_warns(self):
        with mock.patch.object(service, "search_alberta_api", return_value={"values": [row()], "totalCount": 4}) as search:
            rows, warning = service.fetch_all_alberta_opportunities(page_size=1)
        self.assertEqual(search.call_count, 2)
        self.assertIn("repeated a page", warning)

    def test_missing_total_still_pages(self):
        with mock.patch.object(service, "search_alberta_api", side_effect=[
            {"values": [row()]}, {"values": [row("AB-2026-05717")]}, {"values": []}]):
            rows, warning = service.fetch_all_alberta_opportunities(page_size=1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(warning, "")

    def test_time_budget_exhaustion_does_not_start_another_request(self):
        with mock.patch.object(service.time, "monotonic", side_effect=[0, 0, 30]), \
             mock.patch.object(service, "search_alberta_api", return_value={"values": [row()], "totalCount": 2}) as search:
            rows, warning = service.fetch_all_alberta_opportunities(page_size=1, timeout_seconds=20)
        self.assertEqual(search.call_count, 1)
        self.assertIn("time budget", warning)

    def test_fixture_paging_filtering_and_total_match(self):
        payload = {"values": [row(), row("AB-2026-05717"), dict(row("AB-2026-05718"), categoryCode="GD")]}
        first = fixtures.filter_apc_search_payload(payload, category="SRV", limit=1, offset=0, unspsc=["81000000"])
        second = fixtures.filter_apc_search_payload(payload, category="SRV", limit=1, offset=1, unspsc=["81000000"])
        self.assertEqual(first["totalCount"], 2)
        self.assertNotEqual(first["values"], second["values"])


class HarnessContractTests(unittest.TestCase):
    def test_matches_reject_bonus_only_expired_and_out_of_window_rows(self):
        rows = [row(), row("AB-2026-00001", "Snow removal"), row("AB-2026-00002", days=-1), row("AB-2026-00003", days=90)]
        with mock.patch.object(service, "collect_alberta_candidates", return_value=(rows, ["Partial enumeration: fixture"])):
            matches, warnings = service.collect_alberta_matches(PROFILE, 60)
        self.assertEqual([item[2]["referenceNumber"] for item in matches], ["AB-2026-05716"])
        self.assertTrue(warnings)

    def test_structured_matching_and_apc_handler_preserve_warnings_and_references(self):
        with mock.patch.object(service, "collect_alberta_candidates", return_value=([row()], ["Partial enumeration: fixture"])), \
             mock.patch.object(service, "load_contracts_for_unified", return_value=([], [])):
            text, data = asyncio.run(service.call_tool_text_and_structured("find_matching_opportunities", {"profile": PROFILE}))
            apc_text = asyncio.run(service.find_alberta_opportunities({"profile": PROFILE}))
        self.assertEqual(data["matches"][0]["reference"], "AB-2026-05716")
        self.assertEqual(data["warnings"], ["Partial enumeration: fixture"])
        self.assertIn("Partial enumeration", text)
        self.assertIn("Partial enumeration", apc_text)

    def test_structured_search_preserves_planned_order_and_warnings(self):
        with mock.patch.object(service, "collect_alberta_candidates", return_value=(
            [row(), dict(row("AB-2026-05717"), postDateTime="2026-09-25T12:00:00Z")], ["Planner fallback: fixture"])):
            text, data = asyncio.run(service.call_tool_text_and_structured("search_opportunities", {
                "source": "alberta", "keywords": "data platform"}))
        self.assertEqual(data["opportunities"][0]["reference"], "AB-2026-05716")
        self.assertIn("Planner fallback", text)
        self.assertEqual(data["warnings"], ["Planner fallback: fixture"])


if __name__ == "__main__":
    unittest.main()
