"""Oil Sands Growth Program catalog: sourced facts, fit reading, and public-notice matching."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-servers" / "canadabuys"))

from procurement_core.auth import PRO_TOOLS, SIGN_IN_TOOLS
from procurement_core.oil_sands_growth import confirm_official_release, load_catalog
from procurement_core.service import TOOL_NAMES, call_tool_text
from mcp_tools import get_mcp_tools

RELEASE_URL = "https://www.alberta.ca/announcements.cfm?xID=981275DC1AC17-BD32-E06C-F81BC3AE18865A02"
FEDERAL_HEADER = [
    "title-titre-eng",
    "title-titre-fra",
    "referenceNumber-numeroReference",
    "solicitationNumber-numeroSollicitation",
    "publicationDate-datePublication",
    "tenderClosingDate-appelOffresDateCloture",
    "tenderStatus-appelOffresStatut-eng",
    "procurementCategory-categorieApprovisionnement",
    "regionsOfDelivery-regionsLivraison-eng",
    "regionsOfOpportunity-regionAppelOffres-eng",
    "contractingEntityName-nomEntitContractante-eng",
    "tenderDescription-descriptionAppelOffres-eng",
    "noticeURL-URLavis-eng",
]


def _write_fixture(directory: Path, federal_rows: list[dict], alberta_rows: list[dict]) -> None:
    with (directory / "canadabuys-open-tenders.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEDERAL_HEADER)
        writer.writeheader()
        for row in federal_rows:
            writer.writerow(row)
    payload = {"totalCount": len(alberta_rows), "values": alberta_rows}
    (directory / "alberta-apc-search.json").write_text(json.dumps(payload), encoding="utf-8")


def _federal(reference: str, title: str, description: str, buyer: str = "Public Services and Procurement Canada") -> dict:
    return {
        "title-titre-eng": title,
        "title-titre-fra": title,
        "referenceNumber-numeroReference": reference,
        "solicitationNumber-numeroSollicitation": reference,
        "publicationDate-datePublication": "2026-11-01",
        "tenderClosingDate-appelOffresDateCloture": "2026-12-15T14:00:00",
        "tenderStatus-appelOffresStatut-eng": "Open",
        "procurementCategory-categorieApprovisionnement": "Services",
        "regionsOfDelivery-regionsLivraison-eng": "Alberta",
        "regionsOfOpportunity-regionAppelOffres-eng": "Alberta",
        "contractingEntityName-nomEntitContractante-eng": buyer,
        "tenderDescription-descriptionAppelOffres-eng": description,
        "noticeURL-URLavis-eng": f"https://canadabuys.canada.ca/en/tender-opportunities/{reference}",
    }


class OilSandsCatalogTest(unittest.TestCase):
    def test_tools_are_public_listed_and_dispatched(self) -> None:
        names = {
            "get_oil_sands_growth_program",
            "check_oil_sands_growth_fit",
            "find_oil_sands_supply_opportunities",
            "list_oil_sands_growth_updates",
        }
        self.assertTrue(names <= set(TOOL_NAMES))
        listed = {tool.name for tool in get_mcp_tools()}
        self.assertTrue(names <= listed)
        self.assertTrue(names.isdisjoint(PRO_TOOLS))
        self.assertTrue(names.isdisjoint(SIGN_IN_TOOLS))
        self.assertEqual(len(TOOL_NAMES), 33)
        self.assertEqual(len(listed), 20)

    def test_overview_keeps_official_facts_and_gaps(self) -> None:
        text = asyncio.run(call_tool_text("get_oil_sands_growth_program", {}))
        self.assertIn("Oil Sands Growth Program", text)
        self.assertIn("2 per cent", text)
        self.assertIn("6 per cent", text)
        self.assertIn("spring 2027", text)
        self.assertIn("15 November 2026", text)
        self.assertIn("31 December 2029", text)
        self.assertIn(RELEASE_URL, text)
        self.assertIn("Retrieved:** 2026-11-17", text)
        self.assertIn("does not apply", text.lower())
        self.assertIn("No application form", text)
        self.assertIn("not in the written release", text)
        self.assertIn("5,000 barrels", text)
        self.assertIn("https://www.alberta.ca/royalty-oil-sands", text)

    def test_unknown_topic_lists_sections(self) -> None:
        text = asyncio.run(call_tool_text("get_oil_sands_growth_program", {"topic": "budget"}))
        self.assertIn("Unknown topic", text)
        self.assertIn("royalty", text)

    def test_fort_mcmurray_fabricator_is_supply_chain(self) -> None:
        text = asyncio.run(call_tool_text("check_oil_sands_growth_fit", {
            "company_name": "Athabasca Modules",
            "description": "Structural steel fabrication, welding, and pipe modules for plant work",
            "location": "Fort McMurray, Alberta",
        }))
        self.assertIn("not a royalty recipient", text)
        self.assertIn("fort mcmurray", text.lower())
        self.assertIn("does not require local content", text)
        self.assertNotIn("you are eligible", text.lower())

    def test_sagd_fabricator_is_not_treated_as_a_producer(self) -> None:
        text = asyncio.run(call_tool_text("check_oil_sands_growth_fit", {
            "description": "We fabricate modules for SAGD well pads",
            "location": "Nisku, Alberta",
        }))
        self.assertIn("not a royalty recipient", text)
        self.assertNotIn("described itself in producer terms", text)

    def test_producer_reading_stays_unpublished(self) -> None:
        text = asyncio.run(call_tool_text("check_oil_sands_growth_fit", {
            "description": "We are an oil sands producer planning new bitumen production",
            "location": "Calgary, Alberta",
        }))
        self.assertIn("producer terms", text)
        self.assertIn("does not publish the eligibility test", text)

    def test_unrelated_business_has_no_program_path(self) -> None:
        text = asyncio.run(call_tool_text("check_oil_sands_growth_fit", {
            "description": "We bake bread for hospital cafeterias",
            "location": "Red Deer, Alberta",
        }))
        self.assertIn("Nothing in the description matches", text)
        self.assertIn("does not pay unrelated businesses", text)

    def test_supply_finder_matches_public_notices_and_keeps_quotes_separate(self) -> None:
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            _write_fixture(
                folder,
                [
                    _federal(
                        "OSGP-SUNCOR-1",
                        "Module fabrication for a Suncor maintenance campaign",
                        "Shop fabrication of pipe spools for a plant outage.",
                    ),
                    _federal(
                        "OSGP-BAKERY-2",
                        "Cafeteria bread supply",
                        "Fresh bread for a federal cafeteria in Edmonton.",
                    ),
                ],
                [
                    {
                        "referenceNumber": "AB-2026-09901",
                        "title": "Oil sands camp services",
                        "contractingOrganization": "Regional Municipality of Wood Buffalo",
                        "statusCode": "OPEN",
                        "categoryCode": "SRV",
                        "postDateTime": "2026-11-02T15:00:00Z",
                        "closeDateTime": "2026-12-01T15:00:00Z",
                        "regionOfDelivery": ["Wood Buffalo"],
                        "projectDescription": "Camp services supporting oil sands turnaround work near Cenovus operations.",
                    }
                ],
            )
            with patch.dict(os.environ, {"PROCUREMENT_FIXTURE_DIR": directory}):
                text = asyncio.run(call_tool_text("find_oil_sands_supply_opportunities", {"limit": 8}))
                filtered = asyncio.run(call_tool_text("find_oil_sands_supply_opportunities", {
                    "keywords": "camp",
                    "limit": 8,
                }))
        self.assertIn("OSGP-SUNCOR-1", text)
        self.assertIn("AB-2026-09901", text)
        self.assertNotIn("OSGP-BAKERY-2", text)
        self.assertIn("Strathcona", text)
        self.assertIn("125,000", text)
        self.assertIn("None is an approved Oil Sands Growth Program project", text)
        self.assertIn("Why it surfaced:** suncor", text)
        self.assertIn("AB-2026-09901", filtered)
        self.assertNotIn("OSGP-SUNCOR-1", filtered)

    def test_supply_finder_degrades_when_catalogues_have_no_hit(self) -> None:
        with TemporaryDirectory() as directory:
            _write_fixture(Path(directory), [], [])
            with patch.dict(os.environ, {"PROCUREMENT_FIXTURE_DIR": directory}):
                text = asyncio.run(call_tool_text("find_oil_sands_supply_opportunities", {}))
        self.assertIn("No open CanadaBuys", text)
        self.assertIn("Cenovus", text)
        self.assertIn("private procurement", text)

    def test_updates_are_newest_first_and_refresh_failure_keeps_the_copy(self) -> None:
        stored = asyncio.run(call_tool_text("list_oil_sands_growth_updates", {}))
        smith = stored.index("2026-11-17")
        release = stored.index("2026-11-13")
        self.assertLess(smith, release)
        self.assertIn("does not add eligibility rules", stored)
        self.assertIn("https://x.com/ABDanielleSmith/status/2122720163489612027", stored)
        self.assertIn("stored catalog", stored)

        def offline(*_args, **_kwargs):
            raise URLError("offline")

        with patch("procurement_core.oil_sands_growth.urlopen", offline):
            failed = asyncio.run(call_tool_text("list_oil_sands_growth_updates", {"refresh": True}))
        self.assertIn("Live check:** Not confirmed", failed)
        self.assertIn("2026-11-13", failed)
        self.assertIn(RELEASE_URL, failed)

        class Page:
            def read(self, _limit: int) -> bytes:
                return b"A new era of oil sands growth. Oil Sands Growth Program remains posted."

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

        with patch("procurement_core.oil_sands_growth.urlopen", lambda *_args, **_kwargs: Page()):
            confirmed = asyncio.run(call_tool_text("list_oil_sands_growth_updates", {"refresh": "true"}))
        self.assertIn("Live check:** Confirmed", confirmed)
        self.assertIn("No new rules were parsed", confirmed)

    def test_catalog_records_retrieval_date_on_every_source(self) -> None:
        catalog = load_catalog()
        self.assertEqual(catalog["retrieved_on"], "2026-11-17")
        self.assertTrue(catalog["sources"])
        for source in catalog["sources"]:
            self.assertEqual(source["retrieved_on"], "2026-11-17")
            self.assertTrue(source["url"].startswith("https://"))
        check = confirm_official_release(fetch=lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("slow")))
        self.assertEqual(check["ok"], "false")
        self.assertIn("2026-11-17", check["note"])


class OilSandsHttpTest(unittest.TestCase):
    def test_rest_overview_is_public(self) -> None:
        from fastapi.testclient import TestClient
        from server_http import app

        with TestClient(app) as client:
            response = client.post("/oil-sands-growth", json={"topic": "royalty"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["tool"], "get_oil_sands_growth_program")
        self.assertIn("2 per cent", body["content"])
        self.assertIn(RELEASE_URL, body["content"])


if __name__ == "__main__":
    unittest.main()
