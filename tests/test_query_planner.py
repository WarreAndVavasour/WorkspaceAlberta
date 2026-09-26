"""Tests for the Cohere query planner and the APC relevance fixes.

Covers three defects found by reading the live APC API against this code:

1. ``score_alberta_opportunity`` substring-matched whole capability phrases, so
   natural profiles ("custom software development and systems integration")
   never matched anything and scoring collapsed to the region bonus.
2. ``build_alberta_filter`` always sent ``unspsc: []``, discarding APC's native
   commodity-code filter.
3. ``search_alberta_api``'s ``offset`` is a page index, not a row offset, so the
   full corpus was reachable all along but never enumerated.

All network access is monkeypatched; these tests run fully offline.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="canadabuys-test-"))

from procurement_core import query_planner, service  # noqa: E402


NATURAL_PROFILE = {
    "capabilities": [
        "custom software development and systems integration",
        "data platforms, analytics and AI/ML engineering",
    ],
    "location": "Calgary, Alberta",
}

GOOD_OPP = {
    "title": "Request for Proposal - Survey Tool",
    "projectDescription": (
        "Alberta Innovates is seeking proposals for an enterprise survey, data "
        "collection, and reporting platform to support the collection, "
        "management, analysis and reporting of information."
    ),
    "commodityCodeTitles": ["Software", "Business function specific software"],
    "regionOfDelivery": ["Alberta"],
}

BAD_OPP = {
    "title": "Invitation to Bid - 44 Street Widening",
    "projectDescription": "Road widening and utility relocation works.",
    "commodityCodeTitles": ["Heavy construction services"],
    "regionOfDelivery": ["Alberta"],
}


class CapabilityMatchingTests(unittest.TestCase):
    def test_terms_drop_connective_filler(self):
        self.assertEqual(
            service.capability_terms("custom software development and systems integration"),
            ["software", "development", "systems", "integration"],
        )

    def test_morphology_is_tolerated(self):
        # "platforms" must match "platform", "analytics" must match "analysis".
        self.assertTrue(
            service.capability_hit(
                "data platforms, analytics and AI/ML engineering",
                GOOD_OPP["projectDescription"],
            )
        )

    def test_unrelated_text_does_not_match(self):
        self.assertFalse(
            service.capability_hit(
                "data platforms, analytics and AI/ML engineering",
                BAD_OPP["projectDescription"],
            )
        )

    def test_single_word_capability_still_requires_presence(self):
        self.assertTrue(service.capability_hit("software", "enterprise software licence"))
        self.assertFalse(service.capability_hit("software", "snow clearing services"))

    def test_empty_capability_never_matches(self):
        self.assertFalse(service.capability_hit("", "anything at all"))
        self.assertFalse(service.capability_hit("and the for", "anything at all"))


class ScoreAlbertaOpportunityTests(unittest.TestCase):
    """Regression: phrase profiles used to score only the region bonus."""

    def test_relevant_opportunity_scores_above_region_bonus(self):
        score, reasons = service.score_alberta_opportunity(GOOD_OPP, NATURAL_PROFILE)
        self.assertGreater(score, 10, f"expected capability credit, got {reasons}")
        self.assertTrue(any("matches" in r for r in reasons))

    def test_irrelevant_opportunity_gets_region_bonus_only(self):
        score, reasons = service.score_alberta_opportunity(BAD_OPP, NATURAL_PROFILE)
        self.assertEqual(score, 10)
        self.assertEqual(reasons, ["delivers to alberta"])

    def test_relevant_outranks_irrelevant(self):
        good, _ = service.score_alberta_opportunity(GOOD_OPP, NATURAL_PROFILE)
        bad, _ = service.score_alberta_opportunity(BAD_OPP, NATURAL_PROFILE)
        self.assertGreater(good, bad)


class AlbertaFilterTests(unittest.TestCase):
    def test_unspsc_defaults_to_empty(self):
        self.assertEqual(service.build_alberta_filter()["unspsc"], [])

    def test_unspsc_codes_are_plain_strings(self):
        # APC rejects the {"value":..., "selected":...} shape here with a 400.
        filt = service.build_alberta_filter(unspsc=["43000000", "81000000"])
        self.assertEqual(filt["unspsc"], ["43000000", "81000000"])

    def test_blank_codes_are_dropped(self):
        filt = service.build_alberta_filter(unspsc=["43000000", "", "  "])
        self.assertEqual(filt["unspsc"], ["43000000"])


class PagedEnumerationTests(unittest.TestCase):
    def test_pages_until_total_reached(self):
        total = 250

        def fake_search(**kwargs):
            page, limit = kwargs["offset"], kwargs["limit"]
            start = page * limit
            rows = [
                {"referenceNumber": f"AB-2026-{start + i:05d}"}
                for i in range(min(limit, max(0, total - start)))
            ]
            return {"totalCount": total, "values": rows}

        with mock.patch.object(service, "search_alberta_api", side_effect=fake_search):
            rows, warning = service.fetch_all_alberta_opportunities(page_size=100)

        self.assertEqual(len(rows), total)
        self.assertEqual(warning, "")

    def test_partial_enumeration_warns(self):
        def fake_search(**kwargs):
            page, limit = kwargs["offset"], kwargs["limit"]
            return {
                "totalCount": 10_000,
                "values": [{"referenceNumber": f"AB-{page}-{i}"} for i in range(limit)],
            }

        with mock.patch.object(service, "search_alberta_api", side_effect=fake_search):
            rows, warning = service.fetch_all_alberta_opportunities(page_size=100, max_pages=3)

        self.assertEqual(len(rows), 300)
        self.assertIn("Partial enumeration", warning)

    def test_stops_on_empty_page(self):
        def fake_search(**kwargs):
            return {"totalCount": 500, "values": [] if kwargs["offset"] else [{"referenceNumber": "AB-1"}]}

        with mock.patch.object(service, "search_alberta_api", side_effect=fake_search):
            rows, _ = service.fetch_all_alberta_opportunities(page_size=100)

        self.assertEqual(len(rows), 1)


class VocabularyTests(unittest.TestCase):
    def test_codes_roll_up_to_segments_and_sum(self):
        facets = {
            "CommodityCodes": [
                {"value": "43000000", "count": 10},
                {"value": "43230000", "count": 5},
                {"value": "72000000", "count": 20},
            ]
        }
        vocab = query_planner.vocabulary_from_facets(facets)
        self.assertEqual(vocab[0][0], "72000000")
        self.assertEqual(dict((c, n) for c, _, n in vocab)["43000000"], 15)

    def test_malformed_entries_are_skipped(self):
        vocab = query_planner.vocabulary_from_facets({"CommodityCodes": [{"value": "", "count": 3}]})
        self.assertEqual(vocab, [])


def _tool_call_response(arguments: str) -> dict:
    return {
        "choices": [
            {"message": {"tool_calls": [{"function": {"name": "set_opportunity_filter", "arguments": arguments}}]}}
        ]
    }


class PlanQueryTests(unittest.TestCase):
    VOCAB = [("43000000", "IT", 100), ("81000000", "Engineering", 50)]

    def test_parses_tool_call(self):
        payload = (
            '{"unspsc_segments": ["43000000"], "categories": ["SRV"], '
            '"keywords": ["data platform"], "regions": ["Calgary"]}'
        )
        plan = query_planner.plan_query(
            "we build data platforms",
            self.VOCAB,
            api_key="k",
            post_fn=lambda *a, **kw: _tool_call_response(payload),
        )
        self.assertEqual(plan["source"], "cohere")
        self.assertEqual(plan["unspsc"], ["43000000"])
        self.assertEqual(plan["categories"], ["SRV"])
        self.assertEqual(plan["regions"], ["Calgary"])

    def test_codes_outside_vocabulary_are_dropped(self):
        payload = '{"unspsc_segments": ["43000000", "99999999"], "categories": [], "keywords": []}'
        plan = query_planner.plan_query(
            "anything",
            self.VOCAB,
            api_key="k",
            post_fn=lambda *a, **kw: _tool_call_response(payload),
        )
        self.assertEqual(plan["unspsc"], ["43000000"])

    def test_invalid_categories_are_dropped(self):
        payload = '{"unspsc_segments": [], "categories": ["SRV", "NOPE"], "keywords": []}'
        plan = query_planner.plan_query(
            "anything",
            self.VOCAB,
            api_key="k",
            post_fn=lambda *a, **kw: _tool_call_response(payload),
        )
        self.assertEqual(plan["categories"], ["SRV"])

    def test_missing_key_falls_back(self):
        with mock.patch.dict(os.environ, {"COHERE_API_KEY": "", "COHERE_PROD_API_KEY": ""}, clear=False):
            plan = query_planner.plan_query("snow removal services", self.VOCAB, api_key=None)
        self.assertEqual(plan["source"], "fallback")
        self.assertEqual(plan["reason"], "no-api-key")
        self.assertIn("snow", plan["keywords"])

    def test_prose_answer_falls_back(self):
        plan = query_planner.plan_query(
            "snow removal",
            self.VOCAB,
            api_key="k",
            post_fn=lambda *a, **kw: {"choices": [{"message": {"content": "Sure! Here are some ideas."}}]},
        )
        self.assertEqual(plan["source"], "fallback")
        self.assertEqual(plan["reason"], "no-tool-call")

    def test_request_failure_falls_back(self):
        def boom(*_a, **_kw):
            raise RuntimeError("connection reset")

        plan = query_planner.plan_query("snow removal", self.VOCAB, api_key="k", post_fn=boom)
        self.assertEqual(plan["source"], "fallback")
        self.assertEqual(plan["reason"], "request-failed")

    def test_malformed_arguments_fall_back(self):
        plan = query_planner.plan_query(
            "snow removal",
            self.VOCAB,
            api_key="k",
            post_fn=lambda *a, **kw: _tool_call_response("{not json"),
        )
        self.assertEqual(plan["source"], "fallback")
        self.assertEqual(plan["reason"], "bad-arguments")

    def test_tool_choice_is_not_sent(self):
        """command-a-plus 400s on tool_choice; the planner must not send it."""
        captured = {}

        def capture(payload, *_a, **_kw):
            captured.update(payload)
            return _tool_call_response('{"unspsc_segments": [], "categories": [], "keywords": []}')

        query_planner.plan_query("anything", self.VOCAB, api_key="k", post_fn=capture)
        self.assertNotIn("tool_choice", captured)
        self.assertIn("tools", captured)


if __name__ == "__main__":
    unittest.main()
