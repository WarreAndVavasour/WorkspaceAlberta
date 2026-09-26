import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp.types import CallToolRequestParams

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")

from mcp_tools import get_mcp_tools
from procurement_core.agent_contract import SERVER_INSTRUCTIONS
from procurement_core.auth import GateError
from procurement_core.service import TOOL_NAMES, call_tool_text
from server_http import _agent_card, handle_call_tool


class AgentContractTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        telemetry = patch("procurement_core.telemetry.capture", return_value=False)
        telemetry.start()
        self.addCleanup(telemetry.stop)

    async def test_guide_matches_discovery_and_dispatch(self):
        guide = json.loads(await call_tool_text("get_server_guide", {}))
        self.assertEqual(guide, _agent_card("https://example.test")["x-workspacealberta"])
        self.assertFalse(guide["a2a_task_execution"])
        self.assertFalse(guide["training"]["automatic_training"])
        self.assertIn("does not submit bids", SERVER_INSTRUCTIONS[:512])
        self.assertEqual({t.name for t in get_mcp_tools()}, set(TOOL_NAMES))

    async def test_persistent_actions_are_distinguishable_from_search(self):
        tools = {t.name: t for t in get_mcp_tools()}
        self.assertTrue(tools["search_opportunities"].annotations.read_only_hint)
        for name in ("set_business_profile", "watch_opportunity", "unwatch_opportunity"):
            self.assertFalse(tools[name].annotations.read_only_hint)
        self.assertTrue(tools["unwatch_opportunity"].annotations.destructive_hint)

    async def test_denied_access_is_a_tool_error_not_success(self):
        with patch("server_http.check_tool_access", side_effect=GateError(401, "Key required")):
            result = await handle_call_tool(None, CallToolRequestParams(
                name="process_bid_room", arguments={"reference": "test"}))
        self.assertTrue(result.is_error)
        self.assertIn("Key required", result.content[0].text)

    async def test_core_failure_is_a_tool_error(self):
        with patch("server_http.check_tool_access", return_value=None), patch(
            "server_http.call_tool_text_and_structured",
            new=AsyncMock(return_value=("Error: upstream unavailable", None))
        ):
            result = await handle_call_tool(None, CallToolRequestParams(
                name="search_opportunities", arguments={}))
        self.assertTrue(result.is_error)
        self.assertEqual(result.content[0].text, "Error: upstream unavailable")


if __name__ == "__main__":
    unittest.main()
