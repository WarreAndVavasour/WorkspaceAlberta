"""Tests for the extension tools: watchlist and bid/no-bid scorecard."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CANADABUYS_LOAD_ENV_FILE", "0")


class ExtensionToolsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from procurement_core import service

        self._old_data_dir = service.DATA_DIR
        service.DATA_DIR = Path(self._tmp.name)

    def tearDown(self):
        from procurement_core import service

        service.DATA_DIR = self._old_data_dir
        self._tmp.cleanup()

    def test_tool_names_include_extensions(self):
        from procurement_core.service import TOOL_NAMES

        for name in (
            "watch_opportunity",
            "list_watchlist",
            "unwatch_opportunity",
            "bid_no_bid_scorecard",
        ):
            self.assertIn(name, TOOL_NAMES)

    def test_mcp_schemas_match_dispatch(self):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "canadabuys"))
        from mcp_tools import get_mcp_tools
        from procurement_core.service import TOOL_NAMES

        declared = {tool.name for tool in get_mcp_tools()}
        self.assertEqual(declared, set(TOOL_NAMES))

    def test_empty_watchlist(self):
        from procurement_core.service import call_tool_text

        result = asyncio.run(call_tool_text("list_watchlist", {}))
        self.assertIn("empty", result.lower())

    def test_watch_requires_reference(self):
        from procurement_core.service import call_tool_text

        result = asyncio.run(call_tool_text("watch_opportunity", {}))
        self.assertIn("reference", result.lower())

    def test_watch_unwatch_cycle(self):
        from procurement_core.service import call_tool_text

        added = asyncio.run(
            call_tool_text("watch_opportunity", {"reference": "AB-0000-00001", "note": "test note"})
        )
        self.assertIn("AB-0000-00001", added)

        listing = asyncio.run(call_tool_text("list_watchlist", {}))
        self.assertIn("AB-0000-00001", listing)
        self.assertIn("test note", listing)

        duplicate = asyncio.run(call_tool_text("watch_opportunity", {"reference": "AB-0000-00001"}))
        self.assertIn("already", duplicate.lower())

        removed = asyncio.run(call_tool_text("unwatch_opportunity", {"reference": "AB-0000-00001"}))
        self.assertIn("Removed", removed)

        empty = asyncio.run(call_tool_text("list_watchlist", {}))
        self.assertIn("empty", empty.lower())

    def test_scorecard_requires_reference(self):
        from procurement_core.service import call_tool_text

        result = asyncio.run(call_tool_text("bid_no_bid_scorecard", {}))
        self.assertIn("reference", result.lower())

    def test_corrupt_watchlist_tolerated(self):
        from procurement_core import extensions, service

        (service.DATA_DIR / "watchlist.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(extensions.load_watchlist(), [])


if __name__ == "__main__":
    unittest.main()
