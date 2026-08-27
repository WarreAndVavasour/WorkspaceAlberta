import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp-servers" / "canadabuys" / "server.py"
EXPECTED_TOOLS = {
    "set_business_profile",
    "find_opportunities",
    "get_my_profile",
    "search_contracts",
    "get_contract_details",
    "list_upcoming_deadlines",
    "summarize_contracts",
    "refresh_data",
    "search_opportunities",
    "get_opportunity_details",
    "list_deadlines",
    "find_matching_opportunities",
    "daily_bid_brief",
    "process_bid_room",
    "check_cohere_status",
    "analyze_contract_with_cohere",
    "search_alberta_opportunities",
    "get_alberta_opportunity_details",
    "list_alberta_deadlines",
    "summarize_alberta_opportunities",
    "find_alberta_opportunities",
}


class CanadaBuysMcpSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_server_starts_and_answers_a_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as data_dir:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_PATH)],
                cwd=str(ROOT),
                env={
                    **os.environ,
                    "CANADABUYS_DATA_DIR": data_dir,
                },
            )

            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialize_result = await session.initialize()
                    self.assertTrue(initialize_result.server_info.name)

                    tools_result = await session.list_tools()
                    tool_names = {tool.name for tool in tools_result.tools}
                    self.assertTrue(EXPECTED_TOOLS.issubset(tool_names))

                    tool_result = await session.call_tool("get_my_profile", {})
                    self.assertFalse(tool_result.is_error)

                    text_chunks = [
                        content.text
                        for content in tool_result.content
                        if hasattr(content, "text")
                    ]
                    self.assertTrue(text_chunks)

                    status_result = await session.call_tool("check_cohere_status", {})
                    self.assertFalse(status_result.is_error)

                    status_chunks = [
                        content.text
                        for content in status_result.content
                        if hasattr(content, "text")
                    ]
                    self.assertTrue(status_chunks)
                    self.assertIn("This status check does not call the model", status_chunks[0])

    async def test_search_returns_structured_content(self) -> None:
        fixture_dir = ROOT / "tests" / "fixtures" / "procurement"
        with tempfile.TemporaryDirectory() as data_dir:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_PATH)],
                cwd=str(ROOT),
                env={
                    **os.environ,
                    "CANADABUYS_DATA_DIR": data_dir,
                    "PROCUREMENT_FIXTURE_DIR": str(fixture_dir),
                },
            )

            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "search_opportunities",
                        {"keywords": "welding shop Red Deer", "source": "all"},
                    )
                    self.assertFalse(result.is_error)
                    self.assertIsNotNone(result.structured_content)
                    structured = result.structured_content
                    self.assertEqual(structured["kind"], "opportunities")
                    titles = {row["title"] for row in structured["opportunities"]}
                    self.assertIn("Mobile Welding Shop Services - Red Deer, Alberta", titles)
                    self.assertIn("CWB Welding Shop Fit-Up - City of Red Deer", titles)


if __name__ == "__main__":
    unittest.main()
