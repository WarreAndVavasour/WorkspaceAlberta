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
                    self.assertTrue(initialize_result.serverInfo.name)

                    tools_result = await session.list_tools()
                    tool_names = {tool.name for tool in tools_result.tools}
                    self.assertTrue(EXPECTED_TOOLS.issubset(tool_names))

                    tool_result = await session.call_tool("get_my_profile", {})
                    self.assertFalse(tool_result.isError)

                    text_chunks = [
                        content.text
                        for content in tool_result.content
                        if hasattr(content, "text")
                    ]
                    self.assertTrue(text_chunks)


if __name__ == "__main__":
    unittest.main()
