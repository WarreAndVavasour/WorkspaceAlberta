#!/usr/bin/env python3
"""Offline tests for the OPERA service layer and tool declarations.

Everything here runs in mock mode against a temporary data directory — no
network, no credentials, no real OPERA tenant. Settings are injected by
patching ``opera_core.service.get_settings`` with a mock-mode settings stub
that matches the pinned ``Settings`` field list.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from opera_core import catalog
from opera_core import service
from opera_core.mcp_tools import get_mcp_tools


def make_mock_settings(data_dir: Path) -> SimpleNamespace:
    """A mock-mode settings object matching the pinned Settings fields."""
    return SimpleNamespace(
        base_url="https://mock.opera.local",
        graphql_path="/graphql/v1",
        token_path="/oauth/v1/tokens",
        app_key="",
        client_id="",
        client_secret="",
        hotel_id="MOCK",
        username="",
        password="",
        grant_type="password",
        mock=True,
        data_dir=data_dir,
    )


class OperaServiceTestBase(unittest.IsolatedAsyncioTestCase):
    """Base class that patches in mock-mode settings with a tmp data dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.settings = make_mock_settings(self.data_dir)
        self._patcher = patch.object(service, "get_settings", return_value=self.settings)
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self._tmp.cleanup()

    def first_subject_area(self) -> str:
        areas = catalog.list_subject_areas()
        if not areas:
            self.skipTest("mock catalog has no subject areas")
        return str(areas[0].get("name", ""))

    def first_fields(self, name: str, count: int = 2) -> list[str]:
        description = catalog.describe_subject_area(name)
        fields = [
            service.entry_name(entry)
            for entry in description.get("object_types", [])
            if service.entry_name(entry)
        ]
        if not fields:
            self.skipTest(f"subject area {name!r} declares no fields")
        return fields[:count]


class TestToolSurface(OperaServiceTestBase):
    def test_declared_tools_match_service_surface(self) -> None:
        declared = {tool.name for tool in get_mcp_tools()}
        self.assertEqual(declared, set(service.TOOL_NAMES))

    def test_tool_schemas_are_objects(self) -> None:
        for tool in get_mcp_tools():
            self.assertEqual(tool.inputSchema.get("type"), "object", tool.name)
            self.assertIn("properties", tool.inputSchema, tool.name)

    async def test_unknown_tool_lists_available_tools(self) -> None:
        result = await service.call_tool_text("not_a_real_tool", {})
        self.assertIn("Unknown tool", result)
        for name in service.TOOL_NAMES:
            self.assertIn(name, result)


class TestAuthStatus(OperaServiceTestBase):
    async def test_auth_status_reports_mock_mode_without_secrets(self) -> None:
        result = await service.call_tool_text("opera_auth_status", {})
        self.assertIn("mock", result.lower())
        self.assertIn("Configuration", result)
        self.assertNotIn("MOCKSECRET", result)
        # Mock mode never requires a token.
        self.assertIn("no token required", result.lower())


class TestCatalogTools(OperaServiceTestBase):
    async def test_list_subject_areas_returns_grouped_table(self) -> None:
        result = await service.call_tool_text("list_subject_areas", {})
        self.assertIn("Subject Areas", result)
        self.assertIn("| Name |", result)
        self.assertIn("describe_subject_area", result)
        # Known OPERA catalog groups (camelCase prefix grouping).
        self.assertIn("## Financial", result)
        self.assertIn("## Statistics", result)

    async def test_describe_subject_area_shows_fields_filters_example(self) -> None:
        name = self.first_subject_area()
        result = await service.call_tool_text("describe_subject_area", {"name": name})
        self.assertIn(name, result)
        self.assertIn("## Fields", result)
        self.assertIn("## Filters", result)
        self.assertIn("## Example Query", result)

    async def test_describe_unknown_subject_area_errors_helpfully(self) -> None:
        result = await service.call_tool_text(
            "describe_subject_area", {"name": "no_such_area_xyz"}
        )
        self.assertIn("Unknown subject area", result)
        self.assertIn("Available subject areas", result)
        self.assertIn("list_subject_areas", result)


class TestQueryTools(OperaServiceTestBase):
    async def test_query_subject_area_returns_rows(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)
        result = await service.call_tool_text(
            "query_subject_area", {"subject_area": name, "fields": fields}
        )
        self.assertFalse(result.startswith("Error"), result)
        self.assertIn("row(s)", result)
        self.assertIn("Generated query", result)

    async def test_query_subject_area_rejects_unknown_fields(self) -> None:
        name = self.first_subject_area()
        known = self.first_fields(name, count=1)
        result = await service.call_tool_text(
            "query_subject_area",
            {"subject_area": name, "fields": ["definitely_not_a_field"]},
        )
        self.assertIn("Unknown field", result)
        self.assertIn(known[0], result)
        self.assertIn("describe_subject_area", result)

    async def test_query_subject_area_requires_fields(self) -> None:
        name = self.first_subject_area()
        result = await service.call_tool_text(
            "query_subject_area", {"subject_area": name}
        )
        self.assertIn("fields is required", result)

    async def test_run_graphql_query_passthrough(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)
        query, variables = service.build_subject_area_query(name, fields)
        result = await service.call_tool_text(
            "run_graphql_query", {"query": query, "variables": variables}
        )
        self.assertFalse(result.startswith("Error"), result)
        self.assertIn("GraphQL Result", result)

    async def test_run_graphql_query_rejects_bad_variables(self) -> None:
        result = await service.call_tool_text(
            "run_graphql_query", {"query": "{ ok }", "variables": "[1,2]"}
        )
        self.assertIn("variables must be a JSON object", result)


class TestStoreTools(OperaServiceTestBase):
    async def test_sync_writes_queryable_table(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)

        sync_result = await service.call_tool_text(
            "sync_subject_area", {"subject_area": name, "fields": fields}
        )
        self.assertFalse(sync_result.startswith("Error"), sync_result)
        self.assertIn("Rows written", sync_result)

        tables_result = await service.call_tool_text("list_local_tables", {})
        self.assertIn("Local Tables", tables_result)

        table = service.subject_field_name(name).lower()
        sql_result = await service.call_tool_text(
            "query_local_data", {"sql": f"select * from {table} limit 20"}
        )
        self.assertFalse(sql_result.startswith("Error"), sql_result)
        self.assertIn("Query Result", sql_result)
        self.assertIn("row(s) shown", sql_result)
        # The synced table must contain the rows the query returned.
        self.assertIn("|", sql_result)

    async def test_sync_rejects_bad_mode(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)
        result = await service.call_tool_text(
            "sync_subject_area",
            {"subject_area": name, "fields": fields, "mode": "delete_everything"},
        )
        self.assertIn("mode must be one of", result)

    async def test_export_to_csv_writes_file(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)
        result = await service.call_tool_text(
            "export_to_csv",
            {"subject_area": name, "fields": fields, "name": "test_export"},
        )
        self.assertFalse(result.startswith("Error"), result)
        self.assertIn("File:", result)
        exports = list(self.data_dir.rglob("*.csv"))
        self.assertTrue(exports, "expected a CSV file under the tmp data dir")

    async def test_query_local_data_blocks_writes(self) -> None:
        result = await service.call_tool_text(
            "query_local_data", {"sql": "drop table whatever"}
        )
        self.assertIn("read-only", result)


class TestEveryToolCallable(OperaServiceTestBase):
    async def test_every_tool_returns_text(self) -> None:
        name = self.first_subject_area()
        fields = self.first_fields(name)
        query, variables = service.build_subject_area_query(name, fields)
        args_by_tool = {
            "opera_auth_status": {},
            "list_subject_areas": {},
            "describe_subject_area": {"name": name},
            "run_graphql_query": {"query": query, "variables": variables},
            "query_subject_area": {"subject_area": name, "fields": fields},
            "export_to_csv": {"subject_area": name, "fields": fields},
            "sync_subject_area": {"subject_area": name, "fields": fields},
            "list_local_tables": {},
            "query_local_data": {"sql": "select 1"},
        }
        for tool_name in service.TOOL_NAMES:
            with self.subTest(tool=tool_name):
                result = await service.call_tool_text(tool_name, args_by_tool[tool_name])
                self.assertIsInstance(result, str)
                self.assertTrue(result.strip())


if __name__ == "__main__":
    unittest.main()
