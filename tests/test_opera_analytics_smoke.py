import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp-servers" / "opera-analytics" / "server.py"
EXPECTED_TOOLS = {
    "opera_auth_status",
    "list_subject_areas",
    "describe_subject_area",
    "run_graphql_query",
    "query_subject_area",
    "export_to_csv",
    "sync_subject_area",
    "list_local_tables",
    "query_local_data",
}


class OperaAnalyticsMcpSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_server_starts_and_answers_tool_calls(self) -> None:
        with tempfile.TemporaryDirectory() as data_dir:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_PATH)],
                cwd=str(ROOT),
                env={
                    **os.environ,
                    "OPERA_MOCK": "1",
                    "OPERA_DATA_DIR": data_dir,
                    # Force offline behavior regardless of any credentials
                    # present in the parent environment.
                    "OPERA_BASE_URL": "",
                    "OPERA_APP_KEY": "",
                    "OPERA_CLIENT_ID": "",
                    "OPERA_CLIENT_SECRET": "",
                    "OPERA_USERNAME": "",
                    "OPERA_PASSWORD": "",
                },
            )

            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialize_result = await session.initialize()
                    self.assertEqual(initialize_result.serverInfo.name, "opera-analytics")

                    tools_result = await session.list_tools()
                    tool_names = {tool.name for tool in tools_result.tools}
                    self.assertEqual(tool_names, EXPECTED_TOOLS)

                    areas_result = await session.call_tool("list_subject_areas", {})
                    self.assertFalse(areas_result.isError)

                    areas_chunks = [
                        content.text
                        for content in areas_result.content
                        if hasattr(content, "text")
                    ]
                    self.assertTrue(areas_chunks)
                    self.assertIn("Subject Areas", areas_chunks[0])

                    status_result = await session.call_tool("opera_auth_status", {})
                    self.assertFalse(status_result.isError)

                    status_chunks = [
                        content.text
                        for content in status_result.content
                        if hasattr(content, "text")
                    ]
                    self.assertTrue(status_chunks)
                    self.assertIn("OPERA Auth Status", status_chunks[0])
                    self.assertIn("Mock mode", status_chunks[0])


if __name__ == "__main__":
    unittest.main()
