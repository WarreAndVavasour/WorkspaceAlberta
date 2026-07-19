"""Re-run the 5 finding-1 affected trace searches against the LOCAL stdio server.

Uses the fixed local code in mcp-servers/canadabuys/server.py (not the hosted
Cloud Run endpoint) and writes raw results to rerun-finding-1-results.json in
this directory. CANADABUYS_DATA_DIR is pointed at a temp dir so the local
profile/cache state cannot leak into the run.
"""

import asyncio
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "mcp-servers" / "canadabuys" / "server.py"
HERE = Path(__file__).resolve().parent

# (trace_id, tool, arguments) — exact arguments from alberta-usecase-traces.json
SEARCHES = [
    ("uc-04", "search_alberta_opportunities", {"keywords": "catering food service"}),
    ("uc-05", "search_alberta_opportunities", {"keywords": "gravel supply hauling"}),
    ("uc-08", "search_alberta_opportunities", {"keywords": "printing signs"}),
    ("uc-12", "search_opportunities", {"keywords": "snow removal ice control", "province": "Alberta", "limit": 10}),
    ("uc-20", "search_opportunities", {"keywords": "plumbing", "province": "Alberta", "limit": 10}),
    # Single-keyword sanity check: must be unchanged by the fix.
    ("sanity-hvac", "search_alberta_opportunities", {"keywords": "HVAC"}),
]


async def main() -> None:
    with tempfile.TemporaryDirectory() as data_dir:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_PATH)],
            cwd=str(ROOT),
            env={**os.environ, "CANADABUYS_DATA_DIR": data_dir},
        )
        results = {}
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                for trace_id, tool, arguments in SEARCHES:
                    tool_result = await session.call_tool(tool, arguments)
                    text = "\n".join(
                        content.text for content in tool_result.content if hasattr(content, "text")
                    )
                    results[trace_id] = {
                        "tool": tool,
                        "arguments": arguments,
                        "is_error": tool_result.isError,
                        "result_text": text,
                    }
                    header = next((ln for ln in text.splitlines() if ln.strip()), "")
                    print(f"{trace_id}: {tool} {json.dumps(arguments)}")
                    print(f"  error={tool_result.isError} | {header[:110]}")

    out_path = HERE / "rerun-finding-1-results.json"
    with io.open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
