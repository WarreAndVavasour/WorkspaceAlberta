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

        # Stateless mode has no server-push stream; GET must fail fast, not hang.
        mcp_probe = self.client.get("/mcp", headers={"Accept": "text/event-stream"})
        self.assertEqual(mcp_probe.status_code, 405)

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
                "Access-Control-Request-Headers": "content-type,authorization,mcp-session-id",
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

    def test_discovery_endpoints(self) -> None:
        # A2A agent card at every location crawlers have probed.
        for path in (
            "/.well-known/agent.json",
            "/.well-known/agent-card.json",
            "/agents/.well-known/agent-card.json",
            "/mcp/.well-known/agent-card.json",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            card = response.json()
            self.assertEqual(card["name"], "WorkspaceAlberta Procurement")
            self.assertTrue(card["url"].endswith("/mcp"), path)
            skill_ids = {skill["id"] for skill in card["skills"]}
            self.assertIn("search_opportunities", skill_ids)
            self.assertIn("daily_bid_brief", skill_ids)

        # Extended card is spec-correct: 401 + challenge without a key.
        extended = self.client.get("/agent/authenticatedExtendedCard")
        self.assertEqual(extended.status_code, 401)
        self.assertEqual(extended.headers["www-authenticate"], "Bearer")

        # RFC 9728 protected-resource metadata.
        prm = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(prm.status_code, 200)
        self.assertTrue(prm.json()["resource"].endswith("/mcp"))
        self.assertEqual(prm.json()["bearer_methods_supported"], ["header"])

        # RFC 8414 auth-server metadata: honestly not an OAuth AS.
        as_meta = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(as_meta.status_code, 200)
        self.assertIn("issuer", as_meta.json())
        self.assertEqual(as_meta.json()["grant_types_supported"], [])

        # MCP discovery mirrors the registry entry.
        mcp_meta = self.client.get("/.well-known/mcp.json")
        self.assertEqual(mcp_meta.status_code, 200)
        self.assertEqual(mcp_meta.json()["name"], "io.github.HarleyCoops/workspace-alberta")
        self.assertTrue(mcp_meta.json()["remotes"][0]["url"].endswith("/mcp"))


class InlineProfileTest(unittest.TestCase):
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

    def test_profile_arg_declared_on_matching_tools(self) -> None:
        from mcp_tools import get_mcp_tools

        by_name = {tool.name: tool for tool in get_mcp_tools()}
        for name in (
            "find_opportunities",
            "find_matching_opportunities",
            "daily_bid_brief",
            "find_alberta_opportunities",
            "process_bid_room",
            "analyze_contract_with_cohere",
        ):
            self.assertIn("profile", by_name[name].inputSchema["properties"], name)


if __name__ == "__main__":
    unittest.main()
