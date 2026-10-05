"""Read-only acceptance check for a tagged revision or the public MCP endpoint.

Run with the repository dependencies installed. Saves only public tender evidence,
tool names, timings and warnings; no credentials or customer profiles are needed.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

import httpx2

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


PLANNER_TRANSPORT_WARNING = "APC query planner fallback (request-failed); using lexical matching."
CACHE_REFRESH_WARNING = "CanadaBuys cache was empty, so it was refreshed from open data."
RETRYABLE_READS = frozenset({"search_opportunities", "find_matching_opportunities"})
RETRY_DELAYS = (2, 5)


async def call_for_acceptance(client, name, args, report):
    """Retry only an explicit planner transport fallback on two known reads.

    Every attempt remains in the public evidence. This is not a server retry or
    an instruction to hide degraded results: persistent failures still raise,
    all original completeness assertions remain, and writes/auth/schema errors
    are never retried. The retry budget is fixed at two additional calls.
    """
    for attempt in range(1, len(RETRY_DELAYS) + 2):
        started = time.monotonic()
        result = await client.call_tool(name, args)
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        assert not result.is_error and not text.startswith("Error:"), text
        data = result.structured_content
        warnings = data.get("warnings", []) if data else []
        record = {"tool": name, "attempt": attempt,
                  "seconds": round(time.monotonic() - started, 2), "warnings": list(warnings)}
        report["calls"].append(record)
        retryable = (name in RETRYABLE_READS and PLANNER_TRANSPORT_WARNING in warnings
                     and all(w in (PLANNER_TRANSPORT_WARNING, CACHE_REFRESH_WARNING) for w in warnings))
        print(f"Received {name} attempt {attempt} in {record['seconds']}s; warnings={warnings}", flush=True)
        if not retryable:
            return text, data
        if attempt > len(RETRY_DELAYS):
            raise AssertionError(f"Planner transport fallback persisted after {attempt} read attempts: {warnings}")
        record["retry_delay_seconds"] = RETRY_DELAYS[attempt - 1]
        await asyncio.sleep(RETRY_DELAYS[attempt - 1])
    raise AssertionError("Unreachable acceptance retry state")


async def verify(base_url: str) -> dict:
    base_url = base_url.rstrip("/")
    headers = {"User-Agent": "WorkspaceAlberta-Acceptance/1.0"}
    with urlopen(Request(base_url + "/health", headers=headers), timeout=15) as response:
        health = json.load(response)
    assert health["status"] == "ok", health
    report = {"endpoint": base_url, "health": health["status"], "calls": []}
    async with httpx2.AsyncClient(headers=headers, timeout=180) as http_client, \
            streamable_http_client(base_url + "/mcp", http_client=http_client) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=180) as client:
            initialized = await client.initialize()
            assert "commodity filters" in (initialized.instructions or ""), "Server is missing the planner rollout instructions"
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {"search_opportunities", "find_matching_opportunities", "get_opportunity_details"} <= names
            report["tools"] = sorted(names)

            async def call(name, args):
                return await call_for_acceptance(client, name, args, report)

            text, search = await call("search_opportunities", {
                "source": "alberta", "keywords": "data platforms and software engineering", "limit": 5,
            })
            assert search and search["opportunities"], text
            assert not search["warnings"], search["warnings"]
            report["shortlist"] = search["opportunities"]
            reference = search["opportunities"][0]["reference"]
            details, _ = await call("get_opportunity_details", {"reference": reference})
            assert reference in details and "not available" not in details.lower(), details
            report["selected_reference"] = reference
            text, matches = await call("find_matching_opportunities", {"days": 60, "limit": 10,
                "profile": {"description": "data platforms and software engineering",
                            "capabilities": ["software development systems integration", "data platforms analytics"],
                            "location": "Alberta"}})
            assert matches and matches["matches"], text
            assert not any("fallback" in w.lower() or "Partial enumeration" in w for w in matches["warnings"]), matches["warnings"]
            assert any(m["reference"].startswith("AB-") for m in matches["matches"]), matches
            report["matches"] = matches["matches"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(verify(args.url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Acceptance evidence: {args.output}")
