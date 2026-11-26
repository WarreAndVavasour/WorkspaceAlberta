"""Tests for the Victory Garden industrial pivot pipeline, page, and MCP tool."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")
os.environ.setdefault("WA_OAUTH_STORE", "memory")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp-servers" / "canadabuys"))

from procurement_core import victory_garden  # noqa: E402


class VictoryGardenPipelineTest(unittest.TestCase):
    def test_ssrf_blocks_private_and_loopback_hosts(self) -> None:
        for bad in (
            "http://localhost/admin",
            "http://127.0.0.1:8000/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/",
            "ftp://example.com/",
        ):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                victory_garden._validate_public_url(bad)

    def test_crosswalk_maps_cnc_oilfield_shop_and_verifies_stated_certs_only(self) -> None:
        card = victory_garden.analyze_shop_text(
            "Prairie Precision CNC in Nisku, Alberta. 5-axis milling, lathe turning, hydraulic valves, "
            "CWB certified welding bays, and ISO 9001 quality management.",
            website_url="https://prairieprecision.ca",
        )
        self.assertEqual(card["location"], "Edmonton Region, Alberta")
        self.assertIn("CWB Certified", card["stated_certs"])
        self.assertIn("ISO 9001", card["stated_certs"])
        # Must never invent clearances not stated on the site.
        self.assertNotIn("Controlled Goods Program (CGP)", card["stated_certs"])
        cluster_ids = [c["id"] for c in card["matched_clusters"]]
        self.assertIn("precision_machining_defence", cluster_ids)
        self.assertIn("structural_welding_shelters", cluster_ids)

    def test_crosswalk_maps_tarp_and_upholstery_shop_to_field_shelters(self) -> None:
        card = victory_garden.analyze_shop_text(
            "Bow Valley Industrial Canvas & Tarps in Calgary, Alberta — heavy sewing, awnings, truck tarps.",
            website_url="https://bowcanvas.ca",
        )
        cluster_ids = [c["id"] for c in card["matched_clusters"]]
        self.assertEqual(cluster_ids[0], "textiles_shelters_tactical")

    def test_jev_pivot_classifier_parses_verdicts_and_drops_unlikely(self) -> None:
        card = victory_garden.analyze_shop_text(
            "Red Deer CNC machine shop with 5-axis mills and CWB welding in Red Deer, Alberta."
        )
        candidates = [
            {"reference": "CB-1", "title": "DND Marine Hydraulic Valve Assemblies", "buyer": "PSPC"},
            {"reference": "CB-2", "title": "Elementary School Library Books", "buyer": "School Board"},
        ]

        def fake_jev(payload, api_key, max_retries, timeout, **kwargs):
            state = payload["state"]
            if "Hydraulic" in state["notice_title"]:
                return (
                    {
                        "answers": {
                            "pivot_feasibility": {"choice": "subcontract_tier2"},
                            "bridge_type": {"choice": "cert_or_clearance"},
                            "sovereign_lane": {"choice": "defence_security"},
                        }
                    },
                    "",
                    1,
                )
            return (
                {
                    "answers": {
                        "pivot_feasibility": {"choice": "unlikely"},
                        "bridge_type": {"choice": "not_applicable"},
                        "sovereign_lane": {"choice": "general_public"},
                    }
                },
                "",
                1,
            )

        victory_garden._PIVOT_CACHE.clear()
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}), mock.patch.object(
            victory_garden.jev, "call_jev", side_effect=fake_jev
        ):
            verdicts, warnings = victory_garden.classify_pivots_with_jev(card, candidates)
        self.assertEqual(warnings, [])
        self.assertEqual(verdicts["CB-1"]["pivot_feasibility"], "subcontract_tier2")
        self.assertEqual(verdicts["CB-1"]["sovereign_lane"], "defence_security")
        self.assertEqual(verdicts["CB-2"]["pivot_feasibility"], "unlikely")

    def test_victory_garden_brief_result_offline_end_to_end(self) -> None:
        fake_core = (
            "core",
            {
                "kind": "matches",
                "matches": [
                    {
                        "reference": "AB-CORE-1",
                        "title": "Structural Steel Welding Repair",
                        "buyer": "Alberta Transportation",
                        "source": "Alberta APC",
                        "closing_text": "2026-12-20 14:00 Alberta time",
                        "url": "https://purchasing.alberta.ca/posting/AB-CORE-1",
                    }
                ],
                "warnings": [],
            },
        )
        fake_pivot = (
            "pivot",
            {
                "opportunities": [
                    {
                        "reference": "CB-PIVOT-1",
                        "title": "DND Arctic Shelter Frame Fabrication",
                        "buyer": "Department of National Defence",
                        "source": "CanadaBuys",
                        "closing_text": "2027-01-10 14:00 Alberta time",
                        "url": "https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/CB-PIVOT-1",
                        "domestic_policies": ["buy_canadian_materials"],
                    }
                ],
                "warnings": [],
            },
        )

        async def fake_tool(name, args):
            return fake_core if name == "find_matching_opportunities" else fake_pivot

        from procurement_core import service

        with mock.patch.object(service, "call_tool_text_and_structured", side_effect=fake_tool), mock.patch.dict(
            os.environ, {"TYPESAFE_API_KEY": ""}, clear=False
        ):
            md, payload = asyncio.run(
                victory_garden.victory_garden_brief_result(
                    {
                        "company_name": "Red Deer Metalworks",
                        "location": "Red Deer, Alberta",
                        "description": "CWB structural steel welding bays, press brake, and 5-axis CNC lathe.",
                    }
                )
            )
        self.assertEqual(payload["kind"], "victory_garden_brief")
        self.assertEqual(payload["core_count"], 1)
        self.assertEqual(payload["pivot_count"], 1)
        self.assertEqual(payload["pivot_opportunities"][0]["reference"], "CB-PIVOT-1")
        self.assertTrue(payload["support_programs"])
        self.assertIn("Victory Garden Mobilization Brief", md)
        self.assertIn("CB-PIVOT-1", md)


class VictoryGardenHttpAndMcpTest(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        import server_http

        self.client = TestClient(server_http.app)

    def test_tool_is_free_public_and_listed(self) -> None:
        from mcp_tools import get_mcp_tools
        from procurement_core.auth import PRO_TOOLS, SIGN_IN_TOOLS

        names = {t.name for t in get_mcp_tools()}
        self.assertIn("victory_garden_brief", names)
        self.assertNotIn("victory_garden_brief", PRO_TOOLS | SIGN_IN_TOOLS)

    def test_victory_garden_page_and_all_four_archival_plates(self) -> None:
        page = self.client.get("/victory-garden")
        self.assertEqual(page.status_code, 200)
        self.assertIn("18 Months", page.text)
        self.assertIn("Victory Garden", page.text)
        self.assertIn("application/ld+json", page.text)
        for plate in (
            "victory-garden-canada.webp",
            "rosemont-rubber-drive-1942.webp",
            "scrap-metal-magnet-1942.webp",
            "geco-canada-war-factory.webp",
        ):
            self.assertIn(f"/assets/victory-garden/{plate}", page.text)
            asset = self.client.get(f"/assets/victory-garden/{plate}")
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.headers["content-type"], "image/webp")
            self.assertGreater(len(asset.content), 10_000)

        self.assertEqual(self.client.get("/assets/victory-garden/../../secret.txt").status_code, 404)

    def test_post_victory_garden_validates_input_and_returns_brief(self) -> None:
        empty = self.client.post("/victory-garden", json={})
        self.assertEqual(empty.status_code, 422)

        ssrf = self.client.post("/victory-garden", json={"website_url": "http://127.0.0.1:8000"})
        self.assertEqual(ssrf.status_code, 400)

        fake_payload = (
            "# Victory Garden Mobilization Brief",
            {
                "kind": "victory_garden_brief",
                "shop": {"company_name": "Test Fab", "location": "Alberta"},
                "core_count": 1,
                "pivot_count": 2,
                "core_opportunities": [],
                "pivot_lanes": [],
                "pivot_opportunities": [],
                "support_programs": [],
                "warnings": [],
            },
        )
        with mock.patch("procurement_core.victory_garden.victory_garden_brief_result", new=mock.AsyncMock(return_value=fake_payload)):
            ok = self.client.post("/victory-garden", json={"description": "CWB welding shop in Alberta"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["pivot_count"], 2)
        self.assertIn("Victory Garden Mobilization Brief", ok.json()["markdown"])


if __name__ == "__main__":
    unittest.main()
