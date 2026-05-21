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
from server_sse import app  # noqa: E402


class ProcurementHttpAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_tools_openapi_and_generic_tool(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

        tools = self.client.get("/tools")
        self.assertEqual(tools.status_code, 200)
        tool_names = {tool["name"] for tool in tools.json()["tools"]}
        self.assertIn("search_opportunities", tool_names)
        self.assertIn("daily_bid_brief", tool_names)

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/search", openapi.json()["paths"])

        cohere_status = self.client.post("/tools/check_cohere_status", json={})
        self.assertEqual(cohere_status.status_code, 200)
        self.assertIn(
            "This status check does not call the model",
            cohere_status.json()["content"],
        )


if __name__ == "__main__":
    unittest.main()
