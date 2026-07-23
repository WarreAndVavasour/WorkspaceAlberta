"""Production-hardening regression tests: event-loop offload and auth cache bound."""

import threading
import time
import unittest

from procurement_core import auth, service


class EventLoopOffloadTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_handler_runs_off_the_event_loop_thread(self) -> None:
        """Handlers block on urlopen; call_tool_text must not run them on the loop."""
        seen: dict[str, str] = {}

        async def fake_tool(args: dict) -> str:
            seen["thread"] = threading.current_thread().name
            return "ok"

        original = service.summarize_contracts
        service.summarize_contracts = fake_tool
        try:
            result = await service.call_tool_text("summarize_contracts", {})
        finally:
            service.summarize_contracts = original

        self.assertEqual(result, "ok")
        self.assertNotEqual(seen["thread"], threading.main_thread().name)

    async def test_handler_exception_still_returns_error_text(self) -> None:
        async def broken_tool(args: dict) -> str:
            raise RuntimeError("boom")

        original = service.summarize_contracts
        service.summarize_contracts = broken_tool
        try:
            result = await service.call_tool_text("summarize_contracts", {})
        finally:
            service.summarize_contracts = original

        self.assertEqual(result, "Error: boom")


class AuthCacheBoundTest(unittest.TestCase):
    def setUp(self) -> None:
        auth.clear_cache()

    def tearDown(self) -> None:
        auth.clear_cache()

    def test_cache_never_exceeds_bound(self) -> None:
        now = time.time()
        for i in range(auth.MAX_CACHE_ENTRIES + 500):
            auth._cache_put(f"hash-{i}", None, now)
        self.assertLessEqual(len(auth._cache), auth.MAX_CACHE_ENTRIES)

    def test_expired_entries_evicted_before_fresh_ones(self) -> None:
        now = time.time()
        stale = now - auth.CACHE_TTL_SECONDS - 1
        for i in range(auth.MAX_CACHE_ENTRIES):
            auth._cache_put(f"stale-{i}", None, stale)
        auth._cache_put("fresh", {"status": "active"}, now)
        self.assertIn("fresh", auth._cache)
        self.assertLessEqual(len(auth._cache), auth.MAX_CACHE_ENTRIES)
        # The expired flood is gone entirely, not just halved.
        self.assertNotIn("stale-0", auth._cache)


if __name__ == "__main__":
    unittest.main()
