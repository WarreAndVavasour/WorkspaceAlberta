"""Offline regressions for the five connector-directory review findings."""
import asyncio
import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tests.test_procurement_http_app import app
from fastapi.testclient import TestClient
from mcp.types import CallToolRequestParams
from mcp_tools import get_mcp_tools
from server_http import handle_call_tool
from procurement_core import auth, identity, service, storage
from procurement_core.agent_contract import workflow_contract
from procurement_core import e2b_bid_room as bid


class ConnectorDeclarationTest(unittest.TestCase):
    def test_partial_auth_and_legacy_selection_are_unambiguous(self):
        tools = {tool.name: tool for tool in get_mcp_tools()}
        declaration = workflow_contract()["authentication"]
        self.assertEqual(declaration["auth_type"], "none")
        self.assertTrue(declaration["partial_auth"])
        self.assertEqual(set(declaration["sign_in_tools"]), auth.SIGN_IN_TOOLS)
        self.assertEqual(set(declaration["pro_tools"]), auth.PRO_TOOLS)
        for name in ("search_contracts", "get_contract_details", "list_upcoming_deadlines",
                     "summarize_contracts", "find_opportunities"):
            self.assertIn("Legacy:", tools[name].description)
            self.assertIn("federal CanadaBuys", tools[name].description)
        self.assertNotIn("status", tools["search_contracts"].description)
        for name in auth.PROTECTED_TOOLS:
            self.assertIn("sign-in", tools[name].description)
        for name in ("search_alberta_opportunities", "find_alberta_opportunities", "find_matching_opportunities"):
            self.assertIn("sent to Cohere", tools[name].description)
        properties = tools["process_bid_room"].input_schema["properties"]
        self.assertNotIn("timeout_seconds", properties)
        self.assertNotIn("command_timeout_seconds", properties)
        self.assertFalse(tools["process_bid_room"].input_schema["additionalProperties"])


class PartialAuthenticationTest(unittest.TestCase):
    def test_public_discovery_stays_open_and_protected_calls_challenge(self):
        with patch.dict(os.environ, {"WA_HOSTED": "1"}), TestClient(app) as client:
            for name in auth.PROTECTED_TOOLS:
                response = client.post("/mcp", headers={"Accept": "application/json"}, json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": name, "arguments": {}},
                })
                self.assertEqual(response.status_code, 401, name)
                self.assertIn("resource_metadata", response.headers["www-authenticate"])
            self.assertEqual(client.get("/profile").status_code, 401)
            self.assertEqual(client.post("/profile", json={"description": "Steel"}).status_code, 401)
            public = client.post("/mcp", headers={"Accept": "application/json"}, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "get_server_guide", "arguments": {}},
            })
            self.assertEqual(public.status_code, 200)
            self.assertFalse(public.json()["result"].get("isError", False))
            self.assertEqual(client.post("/mcp", headers={"Accept": "application/json"}, json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/list",
            }).status_code, 200)

    def test_free_signed_in_profile_uses_own_tenant_without_pro(self):
        record = {"tenant_id": "user:free-test", "pro_active": False}

        async def profile(_args):
            return storage._current_tenant.get()

        with patch.dict(os.environ, {"WA_HOSTED": "1"}), patch.object(
            identity, "resolve_bearer", return_value=record
        ), patch.object(service, "get_my_profile", new=profile), TestClient(app) as client:
            result = client.get("/profile", headers={"Authorization": "Bearer test-token"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["content"], "user:free-test")
            denied = client.post("/tools/list_watchlist", json={}, headers={"Authorization": "Bearer test-token"})
            self.assertEqual(denied.status_code, 402)
        self.assertIsNone(storage._current_tenant.get())


class BidRoomBoundsTest(unittest.IsolatedAsyncioTestCase):
    async def test_slow_lookup_returns_error_and_cannot_later_start_sandbox(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def slow_details(_reference):
            started.set()
            release.wait(timeout=2)
            return {}

        original = service.process_bid_room_artifact

        def worker(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            finally:
                finished.set()

        with patch.object(bid, "BID_ROOM_CALL_SECONDS", .05), patch.object(
            service, "process_bid_room_artifact", side_effect=worker
        ), patch.object(service, "resolve_profile", return_value={}), patch.object(
            service, "is_alberta_reference", return_value=True
        ), patch.object(service, "get_alberta_api_details", side_effect=slow_details), patch.object(
            bid, "build_apc_bid_room_payload", return_value={}
        ), patch.object(bid, "run_live_bid_room_process") as run:
            before = time.monotonic()
            result = await service.call_tool_text("process_bid_room", {"reference": "APC-TEST"})
            elapsed = time.monotonic() - before
            release.set()
            await asyncio.to_thread(finished.wait, 2)
            self.assertTrue(finished.is_set())
            self.assertTrue(started.is_set())
            self.assertLess(elapsed, 1)
            self.assertTrue(result.startswith("Error:"))
            self.assertIn("no completed analysis", result)
            self.assertIn("max_attachments=1", result)
            run.assert_not_called()

    async def test_timeout_is_an_mcp_tool_error(self):
        with patch("server_http.check_tool_access", return_value=None), patch.object(
            service, "process_bid_room_artifact_bounded", new=AsyncMock(side_effect=bid.BidRoomTimeout(bid.BID_ROOM_TIMEOUT_MESSAGE))
        ), patch("procurement_core.telemetry.capture", return_value=False):
            result = await handle_call_tool(None, CallToolRequestParams(
                name="process_bid_room", arguments={"reference": "test"}))
        self.assertTrue(result.is_error)
        self.assertIn("no completed analysis", result.content[0].text)

    def test_old_rest_options_cannot_extend_execution_or_keep_sandbox_alive(self):
        result = SimpleNamespace(sandbox_id="test", killed=True, artifact={})
        with patch.object(service, "resolve_profile", return_value={}), patch.object(
            service, "is_alberta_reference", return_value=True
        ), patch.object(service, "get_alberta_api_details", return_value={}), patch.object(
            bid, "build_apc_bid_room_payload", return_value={}
        ), patch.object(bid, "run_live_bid_room_process", return_value=result) as run, patch.object(
            bid, "render_bid_room_markdown", return_value="done"
        ):
            before = time.monotonic()
            service.process_bid_room_artifact({"reference": "TEST", "timeout_seconds": 86400,
                "command_timeout_seconds": 3600, "keep_alive": True})
        kwargs = run.call_args.kwargs
        self.assertEqual(set(kwargs), {"deadline"})
        self.assertLessEqual(kwargs["deadline"] - before, bid.BID_ROOM_WORK_SECONDS + .1)

    def test_sandbox_is_killed_when_remote_command_times_out(self):
        from e2b.exceptions import TimeoutException
        sandbox = Mock(sandbox_id="test")
        sandbox.commands.run.side_effect = TimeoutException("command timed out")
        sandbox.kill.return_value = True
        with patch.dict(os.environ, {"E2B_API_KEY": "fixture", "COHERE_API_KEY": "fixture"}), patch.object(
            bid, "load_local_env"
        ), patch("e2b.Sandbox.create", return_value=sandbox) as create:
            with self.assertRaisesRegex(bid.BidRoomTimeout, "no completed analysis"):
                bid.run_live_bid_room_process({}, timeout_seconds=86400,
                    command_timeout_seconds=3600, keep_alive=True)
        self.assertLessEqual(create.call_args.kwargs["timeout"], 130)
        self.assertEqual(create.call_args.kwargs["retries"], 0)
        self.assertLessEqual(sandbox.commands.run.call_args.kwargs["timeout"], 120)
        sandbox.kill.assert_called_once_with(request_timeout=5, retries=0)


if __name__ == "__main__":
    unittest.main()
