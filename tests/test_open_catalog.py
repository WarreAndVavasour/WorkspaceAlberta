"""Open-sector matching, Buy Canadian flags, and the industrial-support catalog."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from procurement_core.domestic_policy import detect_domestic_policies
from procurement_core.requirements import tags
from procurement_core.service import (
    federal_contract_matches,
    normalize_canadabuys_contract,
    resolve_profile,
    score_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def _contract(**fields) -> dict:
    row = {
        "title-titre-eng": "Untitled notice",
        "tenderDescription-descriptionAppelOffres-eng": "",
        "regionsOfDelivery-regionsLivraison-eng": "Alberta",
        "tenderStatus-appelOffresStatut-eng": "Open",
    }
    row.update(fields)
    return row


class OpenIndustryTest(unittest.TestCase):
    def test_steel_description_still_infers_steel(self) -> None:
        profile = resolve_profile({
            "profile": {
                "company_name": "Test Fab",
                "location": "Edmonton, Alberta",
                "description": "structural steel fabrication and welding",
            }
        })
        self.assertIn("steel", profile["industries"])
        self.assertTrue(profile["capabilities"])

    def test_explicit_industry_is_kept_verbatim(self) -> None:
        profile = resolve_profile({
            "profile": {
                "description": "Exploration",
                "industries": ["critical minerals"],
                "capabilities": ["lithium"],
            }
        })
        self.assertEqual(profile["industries"], ["critical minerals"])

    def test_software_and_healthcare_are_first_class(self) -> None:
        profile = resolve_profile({
            "profile": {
                "description": "We build custom software and AI tools for hospitals",
                "location": "Calgary, Alberta",
            }
        })
        self.assertIn("information technology", profile["industries"])
        self.assertIn("healthcare", profile["industries"])

    def test_logistics_is_not_labeled_lumber(self) -> None:
        profile = resolve_profile({
            "profile": {"description": "Regional logistics and freight brokerage"}
        })
        self.assertIn("logistics", profile["industries"])
        self.assertNotIn("lumber", profile["industries"])

    def test_unlisted_trade_gets_a_free_text_label(self) -> None:
        profile = resolve_profile({
            "profile": {"description": "Underwater acoustic monitoring for harbours"}
        })
        self.assertTrue(profile["industries"])
        self.assertNotIn("steel", profile["industries"])
        self.assertTrue(any("acoustic" in label or "underwater" in label for label in profile["industries"]))

    def test_short_token_inside_another_word_is_not_an_industry(self) -> None:
        profile = resolve_profile({
            "profile": {"description": "Available for general labour and snow removal"}
        })
        self.assertNotIn("information technology", profile["industries"])


class ClassificationAndPolicyTest(unittest.TestCase):
    def test_normalize_keeps_source_classification_fields(self) -> None:
        normalized = normalize_canadabuys_contract(_contract(**{
            "title-titre-eng": "Software support",
            "unspsc": "81111500",
            "unspscDescription-eng": "Computer services",
            "gsin-nibs": "N7010",
            "gsinDescription-nibsDescription-eng": "Information technology services",
            "tradeAgreements-accordsCommerciaux-eng": "Canadian Free Trade Agreement (CFTA)",
            "procurementMethod-methodeApprovisionnement-eng": "Open bidding",
            "selectionCriteria-criteresSelection-eng": "Highest combined rating",
        }))
        self.assertEqual(normalized["unspsc"], "81111500")
        self.assertEqual(normalized["unspsc_description"], "Computer services")
        self.assertEqual(normalized["gsin"], "N7010")
        self.assertEqual(normalized["gsin_description"], "Information technology services")
        self.assertEqual(normalized["procurement_method"], "Open bidding")
        self.assertEqual(normalized["selection_criteria"], "Highest combined rating")
        self.assertEqual(normalized["domestic_policies"], ["cfta_domestic_only"])

    def test_search_can_see_gsin_description(self) -> None:
        contract = _contract(**{
            "title-titre-eng": "Standing offer",
            "gsinDescription-nibsDescription-eng": "Janitorial services for hospitals",
        })
        self.assertTrue(federal_contract_matches(contract, "janitorial", "", ""))
        self.assertFalse(federal_contract_matches(contract, "submarine", "", ""))

    def test_policy_flags_are_specific(self) -> None:
        materials = "This construction procurement is subject to the Policy on Prioritizing Canadian Materials in Federal Procurements."
        strategic = "The Policy on Prioritizing Canadian Suppliers and Canadian Content in Strategic Federal Procurements applies above $5 million."
        suppliers = "This tender is limited to Canadian suppliers."
        reciprocal = "The Policy on Reciprocal Procurement applies to this notice."
        self.assertEqual(detect_domestic_policies("", materials), ["buy_canadian_materials"])
        self.assertEqual(detect_domestic_policies("", strategic), ["buy_canadian_strategic"])
        self.assertEqual(detect_domestic_policies("", suppliers), ["canadian_suppliers_only"])
        self.assertEqual(detect_domestic_policies("", reciprocal), ["reciprocal_procurement"])
        self.assertEqual(
            detect_domestic_policies("Canadian Free Trade Agreement (CFTA)"),
            ["cfta_domestic_only"],
        )
        self.assertEqual(
            detect_domestic_policies(
                "Canadian Free Trade Agreement (CFTA), Canada-European Union Comprehensive Economic and Trade Agreement (CETA)"
            ),
            [],
        )
        self.assertEqual(detect_domestic_policies(""), [])
        self.assertEqual(detect_domestic_policies("None"), ["cfta_domestic_only"])
        self.assertEqual(detect_domestic_policies("", "Supply of steel beams"), [])

    def test_canadian_business_is_rewarded_only_on_a_content_match(self) -> None:
        contract = _contract(**{
            "title-titre-eng": "Cloud software development services",
            "tenderDescription-descriptionAppelOffres-eng": (
                "Custom application development. "
                "The Policy on Prioritizing Canadian Suppliers and Canadian Content in Strategic Federal Procurements applies."
            ),
            "tradeAgreements-accordsCommerciaux-eng": "Canadian Free Trade Agreement (CFTA)",
            "unspscDescription-eng": "Computer software",
        })
        alberta = resolve_profile({
            "profile": {
                "description": "We build custom software and AI tools",
                "location": "Calgary, Alberta",
            }
        })
        houston = dict(alberta, location="Houston, Texas")
        alberta_score, alberta_reasons = score_contract(contract, alberta)
        houston_score, houston_reasons = score_contract(contract, houston)
        self.assertGreater(alberta_score, houston_score)
        self.assertTrue(any("domestic preference" in reason for reason in alberta_reasons))
        self.assertFalse(any("domestic preference" in reason for reason in houston_reasons))

        unrelated = {
            "capabilities": ["software"],
            "industries": ["information technology"],
            "location": "Calgary, Alberta",
        }
        office = _contract(**{
            "title-titre-eng": "Office chairs",
            "tenderDescription-descriptionAppelOffres-eng": (
                "Policy on Prioritizing Canadian Materials in Federal Procurements"
            ),
        })
        _score, reasons = score_contract(office, unrelated)
        self.assertFalse(any("domestic preference" in reason for reason in reasons))


class IndustrialCatalogTest(unittest.TestCase):
    def test_tool_is_public_and_dispatched(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "mcp-servers" / "canadabuys"))
        from mcp_tools import get_mcp_tools
        from procurement_core.auth import PRO_TOOLS, SIGN_IN_TOOLS
        from procurement_core.service import TOOL_NAMES

        self.assertIn("match_industrial_support_programs", TOOL_NAMES)
        self.assertIn("match_industrial_support_programs", {tool.name for tool in get_mcp_tools()})
        self.assertNotIn("match_industrial_support_programs", PRO_TOOLS)
        self.assertNotIn("match_industrial_support_programs", SIGN_IN_TOOLS)

    def test_alberta_steel_firm_sees_prairies_and_ontario_only(self) -> None:
        from procurement_core.service import call_tool_text

        text = asyncio.run(call_tool_text("match_industrial_support_programs", {
            "description": "Structural steel fabrication and welding",
            "location": "Edmonton, Alberta",
        }))
        applies, _, ontario = text.partition("## Ontario-only")
        self.assertIn("PrairiesCan Regional Tariff Response Initiative", applies)
        self.assertIn("Strategic Response Fund", applies)
        self.assertNotIn("### Joint Steel Action Fund", applies)
        self.assertIn("### Joint Steel Action Fund", ontario)
        self.assertIn("does not apply to an Alberta business", ontario)

    def test_healthcare_firm_is_not_pushed_into_the_metals_envelope(self) -> None:
        from procurement_core.service import call_tool_text

        text = asyncio.run(call_tool_text("match_industrial_support_programs", {
            "description": "Clinical training for hospital nursing teams",
            "location": "Red Deer, Alberta",
        }))
        applies, _, _ontario = text.partition("## Ontario-only")
        self.assertIn("PrairiesCan Regional Tariff Response Initiative", applies)
        self.assertNotIn("BDC metals envelope", applies)

    def test_versions_are_1_2_0(self) -> None:
        server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
        plugin = json.loads((ROOT / "plugins/workspacealberta/plugin.json").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / "plugins/workspacealberta/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        http = (ROOT / "mcp-servers/canadabuys/server_http.py").read_text(encoding="utf-8")
        self.assertEqual(server["version"], "1.2.0")
        self.assertEqual(plugin["version"], "1.2.0")
        self.assertEqual(claude["version"], "1.2.0")
        self.assertEqual(plugin["version"], claude["version"])
        self.assertIn('version="1.2.0"', http)
        self.assertNotIn("1.1.1", http)
        self.assertLessEqual(len(plugin["extensions"]["com.openai"]["interface"]["longDescription"]), 4000)


class RequirementTagTest(unittest.TestCase):
    def test_canadian_materials_origin_is_a_compliance_tag(self) -> None:
        self.assertIn("canadian_materials_origin", tags.SUB_TAGS["compliance_confirm"])
        routing = tags.routing("compliance_confirm.canadian_materials_origin")
        self.assertEqual(routing["answer_source"], "third_party")
        self.assertEqual(routing["lead_time"], "days")
        self.assertIn("mill test report", routing["question"].lower())


if __name__ == "__main__":
    unittest.main()
