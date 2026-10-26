"""Commodity prefilter and TypeSafe Jev supply fit, including the bakery case."""

from __future__ import annotations

import asyncio
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from procurement_core import business_fit, service
from procurement_core.requirements import jev

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "business_fit"
BAKERY = "bakery in Red Deer, Alberta providing baking at scale and baking/culinary training"
WHEN = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)

RELEVANT = ("CB-BAKERY-001", "CB-CATER-002", "AB-2026-09001", "CB-SUPPLY-003")
UNRELATED = ("CB-SOFT-004", "CB-SCRUB-005", "CB-LAB-006", "CB-DEF-007", "AB-2026-09099")


def frozen_datetime(now: datetime):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    return FrozenDateTime


def _choice(verdict: str, capability: str) -> dict:
    return {
        "answers": {
            "supplies": {
                "choice": verdict,
                "probabilities": {"yes": 0.1, "partial": 0.1, "no": 0.1, verdict: 0.8},
            },
            "capability": {
                "choice": capability,
                "probabilities": {
                    "goods_supply": 0.05,
                    "services": 0.05,
                    "training": 0.05,
                    "subcontract": 0.05,
                    "none": 0.05,
                    capability: 0.8,
                },
            },
        },
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 480},
    }


def bakery_jev(payload, api_key, max_retries=1, timeout=6.0, deadline=None, stop=None):
    del api_key, max_retries, timeout, deadline, stop
    title = str((payload.get("state") or {}).get("notice_title") or "").lower()
    if "bakery products" in title:
        verdict, capability = "yes", "goods_supply"
    elif "catering" in title or "food services" in title:
        verdict, capability = "yes", "services"
    elif "supply arrangement" in title or "food-service" in title or "food service supply" in title:
        verdict, capability = "partial", "goods_supply"
    else:
        verdict, capability = "no", "none"
    return _choice(verdict, capability), "", 1


class PrefilterTests(unittest.TestCase):
    def test_bakery_expansion_drops_bare_food_and_training_words(self) -> None:
        expansion = business_fit.expand(BAKERY)
        self.assertIn("bakery goods", expansion.labels)
        self.assertIn("culinary training", expansion.labels)
        self.assertIn("food service", expansion.labels)
        self.assertNotIn("food", expansion.terms)
        self.assertNotIn("training", expansion.terms)
        self.assertTrue(any(prefix.startswith("5018") or prefix == "501817" for prefix in expansion.prefixes))

    def test_bakery_candidates_exclude_the_smoke_test_misses(self) -> None:
        expansion = business_fit.expand(BAKERY)
        notices = [
            {"reference": "bakery", "title": "Bakery products", "unspsc": "50181701", "description": "bread"},
            {"reference": "catering", "title": "Catering and food services", "unspsc": "90101601", "description": ""},
            {"reference": "supply", "title": "Food-service supply arrangement", "unspsc": "", "description": ""},
            {"reference": "software", "title": "Software licences", "unspsc": "43230000", "description": ""},
            {"reference": "scrub", "title": "Floor scrubbers", "unspsc": "47121600", "description": ""},
            {
                "reference": "lab",
                "title": "Laboratory building for agri-food research",
                "buyer": "Agriculture and Agri-Food Canada",
                "unspsc": "72101500",
                "description": "Construction of a laboratory building for agri-food research.",
            },
            {
                "reference": "defence",
                "title": "Training facility construction",
                "unspsc": "72101500",
                "description": "Construction of a training facility. Not a culinary or baking program.",
            },
            {
                "reference": "body-only",
                "title": "Standing offer",
                "unspsc": "",
                "description": "Supply of fresh bakery products for federal kitchens.",
            },
        ]
        chosen, total = business_fit.select_candidates(notices, expansion)
        refs = [item["reference"] for item in chosen]
        self.assertEqual(set(refs), {"bakery", "catering", "supply"})
        self.assertEqual(total, 3)
        for missing in ("software", "scrub", "lab", "defence", "body-only"):
            self.assertNotIn(missing, refs)


class JevClientTests(unittest.TestCase):
    def setUp(self) -> None:
        business_fit.clear_cache()

    def test_missing_key_does_not_call(self) -> None:
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "", "JEV_API_KEY": ""}), \
             mock.patch.object(jev, "call_jev") as call:
            result = business_fit.classify_notices(
                {"description": BAKERY, "location": "Red Deer, Alberta"},
                [{"reference": "CB-BAKERY-001", "title": "Bakery products", "description": "bread"}],
            )
        call.assert_not_called()
        self.assertEqual(result.status, "unconfigured")
        self.assertIn("keyword ranking", result.warnings[0])

    def test_auth_failure_is_a_fallback_status(self) -> None:
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "secret-key", "JEV_API_KEY": ""}), \
             mock.patch.object(jev, "call_jev", side_effect=jev.AuthError("HTTP 401: rejected")):
            result = business_fit.classify_notices(
                {"description": BAKERY},
                [{"reference": "CB-BAKERY-001", "title": "Bakery products"}],
            )
        self.assertEqual(result.status, "unauthenticated")
        self.assertNotIn("secret-key", result.warnings[0])

    def test_answers_are_cached_per_notice_and_description(self) -> None:
        notice = [{"reference": "CB-BAKERY-001", "title": "Bakery products", "description": "bread"}]
        profile = {"description": BAKERY, "location": "Red Deer, Alberta"}
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "secret-key", "JEV_API_KEY": ""}), \
             mock.patch.object(jev, "call_jev", side_effect=bakery_jev) as call:
            first = business_fit.classify_notices(profile, notice)
            second = business_fit.classify_notices(profile, notice)
        self.assertEqual(call.call_count, 1)
        self.assertEqual(first.verdicts["CB-BAKERY-001"]["verdict"], "yes")
        self.assertEqual(first.verdicts["CB-BAKERY-001"]["capability"], "goods_supply")
        self.assertEqual(second.verdicts["CB-BAKERY-001"]["verdict"], "yes")
        sent = call.call_args.args[0]
        self.assertEqual(sent["questions"], business_fit.FIT_QUESTIONS)
        self.assertIn("baking", sent["state"]["business"])
        self.assertEqual(list(business_fit.FIT_QUESTIONS["supplies"]["criteria"])[-1], "no")
        self.assertEqual(list(business_fit.FIT_QUESTIONS["capability"]["criteria"])[-1], "none")


class BakeryRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        business_fit.clear_cache()
        self.env = mock.patch.dict(os.environ, {
            "PROCUREMENT_FIXTURE_DIR": str(FIXTURE),
            "TYPESAFE_API_KEY": "test-key",
            "JEV_API_KEY": "",
            "CANADABUYS_LOAD_ENV_FILE": "0",
            "COHERE_API_KEY": "",
            "COHERE_PROD_API_KEY": "",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = mock.patch.object(service, "datetime", frozen_datetime(WHEN))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.jev = mock.patch.object(jev, "call_jev", side_effect=bakery_jev)
        self.call = self.jev.start()
        self.addCleanup(self.jev.stop)

    def _refs(self, text: str) -> list[str]:
        return [line.split("`", 2)[1] for line in text.splitlines() if line.strip().startswith("Reference:")]

    def test_bakery_description_ranks_food_notices_above_unrelated(self) -> None:
        text = asyncio.run(service.find_business_fit({
            "description": BAKERY,
            "location": "Red Deer, Alberta",
            "company_name": "Red Deer Bakery",
        }))
        refs = self._refs(text)
        self.assertEqual(refs[0], "CB-BAKERY-001")
        for ref in ("CB-CATER-002", "AB-2026-09001"):
            self.assertLess(refs.index("CB-BAKERY-001"), refs.index(ref))
            self.assertLess(refs.index(ref), refs.index("CB-SUPPLY-003"))
        for ref in UNRELATED:
            self.assertNotIn(ref, refs)
        self.assertIn("Fit: yes (goods supply)", text)
        self.assertIn("Fit: partial (goods supply)", text)
        self.assertIn("domestic preference", text)
        self.assertIn("Buy Canadian", text)
        titles = [
            (call.args[0].get("state") or {}).get("notice_title", "")
            for call in self.call.call_args_list
        ]
        blob = " ".join(titles).lower()
        self.assertIn("bakery products", blob)
        for banned in ("software", "scrubber", "laboratory", "training facility"):
            self.assertNotIn(banned, blob)
        self.assertLessEqual(self.call.call_count, business_fit.MAX_CANDIDATES)
        self.assertNotIn("keyword ranking", text.lower())

    def test_search_opportunities_uses_the_same_pass_when_a_description_is_present(self) -> None:
        text, structured = asyncio.run(service.call_tool_text_and_structured("search_opportunities", {
            "description": BAKERY,
            "location": "Red Deer, Alberta",
        }))
        refs = [row["reference"] for row in structured["opportunities"]]
        self.assertEqual(refs[0], "CB-BAKERY-001")
        self.assertIn("CB-SUPPLY-003", refs)
        self.assertEqual(structured["opportunities"][0]["fit_verdict"], "yes")
        self.assertEqual(structured["opportunities"][0]["fit_capability"], "goods_supply")
        for ref in UNRELATED:
            self.assertNotIn(ref, text)

    def test_keyword_only_search_does_not_call_jev(self) -> None:
        self.call.reset_mock()
        asyncio.run(service.search_opportunities({"keywords": "catering", "limit": 5}))
        self.call.assert_not_called()


class FallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        business_fit.clear_cache()
        self.clock = mock.patch.object(service, "datetime", frozen_datetime(WHEN))
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_missing_key_falls_back_and_warns(self) -> None:
        with mock.patch.dict(os.environ, {
            "PROCUREMENT_FIXTURE_DIR": str(FIXTURE),
            "TYPESAFE_API_KEY": "",
            "JEV_API_KEY": "",
            "CANADABUYS_LOAD_ENV_FILE": "0",
            "COHERE_API_KEY": "",
        }), mock.patch.object(jev, "call_jev") as call:
            text = asyncio.run(service.find_business_fit({
                "description": BAKERY,
                "location": "Red Deer, Alberta",
            }))
        call.assert_not_called()
        self.assertIn("TypeSafe Jev is not configured", text)
        self.assertIn("keyword ranking", text)

    def test_rejected_key_falls_back_without_echoing_the_key(self) -> None:
        with mock.patch.dict(os.environ, {
            "PROCUREMENT_FIXTURE_DIR": str(FIXTURE),
            "TYPESAFE_API_KEY": "super-secret",
            "JEV_API_KEY": "",
            "CANADABUYS_LOAD_ENV_FILE": "0",
            "COHERE_API_KEY": "",
        }), mock.patch.object(jev, "call_jev", side_effect=jev.AuthError("HTTP 401")):
            text = asyncio.run(service.find_matching_opportunities({
                "profile": {
                    "description": BAKERY,
                    "location": "Red Deer, Alberta",
                    "company_name": "Red Deer Bakery",
                },
                "days": 120,
            }))
        self.assertIn("rejected this server's API key", text)
        self.assertIn("keyword ranking", text)
        self.assertNotIn("super-secret", text)


class ProgramDescriptionTests(unittest.TestCase):
    def setUp(self) -> None:
        business_fit.clear_cache()

    def test_bakery_reason_uses_the_description(self) -> None:
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "", "JEV_API_KEY": ""}):
            text = asyncio.run(service.match_industrial_support_programs({
                "description": BAKERY,
                "location": "Red Deer, Alberta",
            }))
        applies, _, ontario = text.partition("## Ontario-only")
        self.assertNotIn("open across industries", text)
        self.assertIn("bakery goods", applies)
        self.assertIn("culinary training", applies)
        self.assertIn("PrairiesCan Regional Tariff Response Initiative", applies)
        self.assertNotIn("BDC metals envelope", applies)
        self.assertIn("### Joint Steel Action Fund", ontario)

    def test_jev_program_verdict_is_part_of_why_it_surfaced(self) -> None:
        def answer(payload, api_key, max_retries=1, timeout=6.0, deadline=None, stop=None):
            del api_key, max_retries, timeout, deadline, stop
            return {
                "answers": {"relevance": {"choice": "partial", "probabilities": {"partial": 0.7, "yes": 0.2, "no": 0.1}}},
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 200},
            }, "", 1

        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key", "JEV_API_KEY": ""}), \
             mock.patch.object(jev, "call_jev", side_effect=answer) as call:
            text = asyncio.run(service.match_industrial_support_programs({
                "description": "Structural steel fabrication and welding",
                "location": "Edmonton, Alberta",
            }))
        self.assertIn("classifier: partial", text)
        self.assertLessEqual(call.call_count, business_fit.MAX_PROGRAMS)
        self.assertIn("steel", call.call_args.args[0]["state"]["business"].lower())


if __name__ == "__main__":
    unittest.main()
