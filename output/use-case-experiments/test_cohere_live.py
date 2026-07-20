#!/usr/bin/env python3
"""One-shot live test: analyze_contract_with_cohere on an Alberta reference."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "mcp-servers" / "canadabuys" / "server.py"


async def main() -> None:
    with tempfile.TemporaryDirectory() as data_dir:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER)],
            cwd=str(ROOT),
            env={**os.environ, "CANADABUYS_DATA_DIR": data_dir},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                status = await session.call_tool("check_cohere_status", {})
                print("=== check_cohere_status ===")
                print("\n".join(c.text for c in status.content if hasattr(c, "text"))[:800])
                print("\n=== analyze_contract_with_cohere AB-2026-04073 ===")
                res = await session.call_tool(
                    "analyze_contract_with_cohere", {"reference": "AB-2026-04073"}
                )
                text = "\n".join(c.text for c in res.content if hasattr(c, "text"))
                print(f"is_error={res.isError} len={len(text)}")
                print(text[:2500])


asyncio.run(main())
