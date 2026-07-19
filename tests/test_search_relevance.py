"""Pure-function tests for the token-coverage relevance helpers.

These tests cover the multi-word search relevance fix (finding #1):
AND-token coverage for Alberta APC rows and the federal contract matcher.
No network access is used.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keep imports side-effect free (service.py creates DATA_DIR at import time).
os.environ.setdefault("CANADABUYS_DATA_DIR", tempfile.mkdtemp(prefix="canadabuys-test-"))

from procurement_core.service import (  # noqa: E402
    alberta_opportunity_text,
    alberta_posted_date,
    federal_contract_matches,
    rank_by_token_coverage,
    token_coverage,
    token_in_text,
    tokenize_keywords,
)


def make_row(title, posted, description="", organization="", commodity_titles=None):
    return {
        "title": title,
        "shortTitle": "",
        "contractingOrganization": organization,
        "projectDescription": description,
        "commodityCodeTitles": commodity_titles or [],
        "postDateTime": posted,
    }


row_date = alberta_posted_date


class TokenizeKeywordsTest(unittest.TestCase):
    def test_splits_and_lowercases(self):
        self.assertEqual(tokenize_keywords("Catering FOOD Service"), ["catering", "food", "service"])

    def test_drops_short_tokens_and_stopwords(self):
        self.assertEqual(tokenize_keywords("snow and ice control for the city"), ["snow", "ice", "control", "city"])

    def test_drops_punctuation_and_dedupes(self):
        self.assertEqual(tokenize_keywords("gravel, supply / gravel"), ["gravel", "supply"])

    def test_empty_input(self):
        self.assertEqual(tokenize_keywords(""), [])
        self.assertEqual(tokenize_keywords(None), [])


class TokenInTextTest(unittest.TestCase):
    def test_word_boundary_match(self):
        self.assertTrue(token_in_text("ice", "snow and ice control"))
        self.assertFalse(token_in_text("ice", "janitorial service contract"))

    def test_plural_tolerance(self):
        self.assertTrue(token_in_text("signs", "supply of street sign materials"))
        self.assertTrue(token_in_text("services", "security service contract"))

    def test_substring_inside_word_not_matched(self):
        self.assertFalse(token_in_text("print", "footprint analysis"))


class TokenCoverageTest(unittest.TestCase):
    def test_full_and_partial(self):
        tokens = ["catering", "food", "service"]
        self.assertEqual(token_coverage("catering and food service contract", tokens), 1.0)
        self.assertAlmostEqual(token_coverage("food service only", tokens), 2 / 3)
        self.assertEqual(token_coverage("unrelated text", tokens), 0.0)

    def test_no_tokens_is_full_coverage(self):
        self.assertEqual(token_coverage("anything", []), 1.0)


class RankByTokenCoverageTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            make_row("Gravel supply and hauling", "2026-01-01T00:00:00Z"),
            make_row("Gravel crushing - supply only", "2026-03-01T00:00:00Z"),
            make_row("Hauling gravel and supply of aggregate", "2026-02-01T00:00:00Z"),
            make_row("Marketing strategy", "2026-04-01T00:00:00Z"),
        ]

    def test_full_coverage_rows_kept_and_sorted_by_recency(self):
        ranked, warning = rank_by_token_coverage(
            self.rows, "gravel supply hauling", alberta_opportunity_text, row_date
        )
        self.assertEqual(warning, "")
        titles = [row["title"] for row in ranked]
        self.assertEqual(
            titles,
            ["Hauling gravel and supply of aggregate", "Gravel supply and hauling"],
        )

    def test_single_token_passthrough_unchanged(self):
        ranked, warning = rank_by_token_coverage(
            self.rows, "gravel", alberta_opportunity_text, row_date
        )
        self.assertEqual(warning, "")
        self.assertEqual([row["title"] for row in ranked], [row["title"] for row in self.rows])

    def test_fallback_when_no_full_coverage(self):
        rows = [
            make_row("Snow plowing", "2026-01-01T00:00:00Z"),
            make_row("Snow removal and ice control", "2026-02-01T00:00:00Z"),
            make_row("Landscaping", "2026-03-01T00:00:00Z"),
        ]
        ranked, warning = rank_by_token_coverage(
            rows, "snow removal winging", alberta_opportunity_text, row_date
        )
        # Nothing matches all tokens, so everything is kept, best coverage first.
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0]["title"], "Snow removal and ice control")
        self.assertEqual(ranked[1]["title"], "Snow plowing")
        self.assertIn("fallback", warning.lower())

    def test_coverage_uses_description_org_and_commodities(self):
        rows = [
            make_row(
                "Untitled posting",
                "2026-01-01T00:00:00Z",
                description="includes catering of food",
                organization="City Service Department",
            ),
            make_row("Something else", "2026-02-01T00:00:00Z", commodity_titles=["Catering"]),
        ]
        ranked, warning = rank_by_token_coverage(
            rows, "catering food service", alberta_opportunity_text, row_date
        )
        self.assertEqual(warning, "")
        self.assertEqual([row["title"] for row in ranked], ["Untitled posting"])


class FederalContractMatchesTest(unittest.TestCase):
    def make_contract(self, title, description=""):
        # Minimal row shape consumed by normalize_canadabuys_contract.
        return {
            "title-titre-eng": title,
            "tenderDescription-descriptionAppelOffres-eng": description,
            "regionsOfDelivery-regionsLivraison-eng": "Alberta",
        }

    def test_single_word_behavior_unchanged_substring(self):
        contract = self.make_contract("Security Services for Airport")
        self.assertTrue(federal_contract_matches(contract, "security", "", ""))
        self.assertFalse(federal_contract_matches(contract, "plumbing", "", ""))

    def test_multiword_all_tokens_any_order(self):
        contract = self.make_contract("Guard and Security Services", "On-site guard services")
        self.assertTrue(federal_contract_matches(contract, "security guard services", "", ""))

    def test_multiword_missing_token_rejected(self):
        contract = self.make_contract("Security Services")
        self.assertFalse(federal_contract_matches(contract, "security guard services", "", ""))

    def test_multiword_stopwords_not_required(self):
        contract = self.make_contract("Snow Removal and Ice Control")
        self.assertTrue(federal_contract_matches(contract, "snow removal and the ice control", "", ""))


if __name__ == "__main__":
    unittest.main()
