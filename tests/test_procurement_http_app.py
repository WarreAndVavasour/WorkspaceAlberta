import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "mcp-servers" / "canadabuys"
TEST_DATA_DIR = tempfile.TemporaryDirectory()

os.environ["CANADABUYS_DATA_DIR"] = TEST_DATA_DIR.name
sys.path.insert(0, str(SERVER_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from server_http import app  # noqa: E402


class ProcurementHttpAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_health_tools_openapi_and_generic_tool(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        health_body = health.json()
        self.assertEqual(health_body["status"], "ok")
        self.assertEqual(health_body["mcp"], {"streamable_http": "/mcp"})

        old_sse = self.client.get("/sse")
        self.assertEqual(old_sse.status_code, 404)

        mcp_probe = self.client.get("/mcp", headers={"Accept": "text/event-stream"})
        self.assertNotEqual(mcp_probe.status_code, 500)

        tools = self.client.get("/tools")
        self.assertEqual(tools.status_code, 200)
        tool_names = {tool["name"] for tool in tools.json()["tools"]}
        self.assertIn("search_opportunities", tool_names)
        self.assertIn("daily_bid_brief", tool_names)
        self.assertIn("process_bid_room", tool_names)

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/search", openapi.json()["paths"])
        self.assertIn("/bid-room/process", openapi.json()["paths"])

        missing_reference = self.client.post("/bid-room/process", json={})
        self.assertEqual(missing_reference.status_code, 400)
        self.assertIn("reference", missing_reference.json()["detail"].lower())

        cohere_status = self.client.post("/tools/check_cohere_status", json={})
        self.assertEqual(cohere_status.status_code, 200)
        self.assertIn(
            "This status check does not call the model",
            cohere_status.json()["content"],
        )

    def test_landing_page(self) -> None:
        landing = self.client.get("/")
        self.assertEqual(landing.status_code, 200)
        self.assertIn("text/html", landing.headers["content-type"])
        self.assertIn("/mcp", landing.text)
        self.assertIn("mcpServers", landing.text)

    def test_cors_preflight(self) -> None:
        preflight = self.client.options(
            "/mcp",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,mcp-session-id",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers["access-control-allow-origin"], "*")

    def test_mcp_stateless_json_only_accept(self) -> None:
        initialize = self.client.post(
            "/mcp",
            headers={"Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        self.assertEqual(initialize.status_code, 200)
        self.assertEqual(initialize.json()["result"]["serverInfo"]["name"], "canadabuys")

        # Stateless: a fresh request with no mcp-session-id header still works.
        tools = self.client.post(
            "/mcp",
            headers={"Accept": "application/json"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        self.assertEqual(tools.status_code, 200)
        tool_names = {tool["name"] for tool in tools.json()["result"]["tools"]}
        self.assertIn("search_opportunities", tool_names)


class PublicModeTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["WORKSPACEALBERTA_PUBLIC_MODE"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("WORKSPACEALBERTA_PUBLIC_MODE", None)

    def test_profile_storage_tools_hidden(self) -> None:
        from mcp_tools import get_mcp_tools

        tool_names = {tool.name for tool in get_mcp_tools()}
        self.assertNotIn("set_business_profile", tool_names)
        self.assertNotIn("get_my_profile", tool_names)
        self.assertIn("find_matching_opportunities", tool_names)

    def test_profile_storage_tools_blocked(self) -> None:
        import asyncio

        from procurement_core.service import call_tool_text

        result = asyncio.run(call_tool_text("set_business_profile", {"description": "steel shop"}))
        self.assertIn("does not store per-user business profiles", result)

    def test_inline_profile_resolves(self) -> None:
        from procurement_core.service import resolve_profile

        profile = resolve_profile(
            {
                "profile": {
                    "company_name": "Test Fab",
                    "location": "Edmonton, Alberta",
                    "description": "structural steel fabrication and welding",
                }
            }
        )
        self.assertEqual(profile["company_name"], "Test Fab")
        self.assertIn("steel", profile["industries"])
        self.assertTrue(profile["capabilities"])


if __name__ == "__main__":
    unittest.main()
