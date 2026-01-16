#!/usr/bin/env python3
"""
CanadaBuys MCP Server - SSE/HTTP Transport

Exposes the CanadaBuys MCP server over HTTP with SSE transport.
This allows remote access from E2B sandboxes via Anthropic's MCP connector.

Usage:
    uvicorn server_sse:app --host 0.0.0.0 --port 8000

    Or for quick testing with ngrok:
    ngrok http 8000
"""

import csv
import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse

# Initialize MCP server
server = Server("canadabuys")

# Configuration
DATA_DIR = Path(os.environ.get("CANADABUYS_DATA_DIR", Path.home() / ".canadabuys"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# CanadaBuys open data URL
OPEN_TENDERS_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

REQUEST_HEADERS = {
    "User-Agent": "CanadaBuys-MCP/1.0",
    "Accept": "*/*",
}


def parse_date(value: str) -> datetime | None:
    """Parse a date string into a datetime object."""
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        pass
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None


def fetch_all_contracts() -> list[dict]:
    """Fetch all contracts from CanadaBuys."""
    request = Request(OPEN_TENDERS_URL, headers=REQUEST_HEADERS)

    with urlopen(request, timeout=120) as response:
        raw_data = response.read()

        if raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)

        text_data = raw_data.decode("utf-8-sig")
        lines = [line for line in text_data.split('\n') if line.strip()]
        if not lines:
            return []

        reader = csv.DictReader(lines)
        return list(reader)


def load_cached_contracts() -> list[dict]:
    """Load contracts from local cache."""
    cache_path = DATA_DIR / "latest.csv"
    if not cache_path.exists():
        return []

    with cache_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_contracts(contracts: list[dict]) -> Path:
    """Save contracts to local cache."""
    latest_path = DATA_DIR / "latest.csv"

    if not contracts:
        return latest_path

    fieldnames = [k for k in contracts[0].keys() if k is not None]

    with latest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(contracts)

    return latest_path


# ============================================================
# MCP TOOLS
# ============================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_contracts",
            description="Search Canadian federal government contracts by keywords, province, or status",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Keywords to search in title and description"
                    },
                    "province": {
                        "type": "string",
                        "description": "Province code (e.g., AB, ON, BC)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 10)"
                    }
                }
            }
        ),
        Tool(
            name="get_contract_details",
            description="Get full details for a specific contract by reference number",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Contract reference or solicitation number"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_upcoming_deadlines",
            description="List contracts with upcoming closing deadlines",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show contracts closing within N days (default: 30)"
                    },
                    "province": {
                        "type": "string",
                        "description": "Filter by province code"
                    }
                }
            }
        ),
        Tool(
            name="refresh_data",
            description="Refresh contract data from CanadaBuys (may take a minute)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="summarize_contracts",
            description="Get a summary of available contracts",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "search_contracts":
        contracts = load_cached_contracts()
        if not contracts:
            contracts = fetch_all_contracts()
            save_contracts(contracts)

        keywords = arguments.get("keywords", "").lower()
        province = arguments.get("province", "").upper()
        limit = arguments.get("limit", 10)

        results = []
        for contract in contracts:
            # CanadaBuys CSV uses bilingual column names
            title = contract.get("title-titre-eng", "").lower()
            desc = contract.get("description-eng", contract.get("gsinDescription-nibsDescription-eng", "")).lower()
            region = contract.get("regionDelivery-regionLivraison-eng", "").upper()

            if keywords and keywords not in title and keywords not in desc:
                continue
            if province and province not in region:
                continue

            results.append({
                "reference": contract.get("referenceNumber-numeroReference", "N/A"),
                "title": contract.get("title-titre-eng", "N/A")[:100],
                "closing_date": contract.get("tenderClosingDate-appelOffresDateCloture", "N/A"),
                "region": region,
                "value": contract.get("estimatedValue-valeurEstimee", "N/A")
            })

            if len(results) >= limit:
                break

        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "get_contract_details":
        reference = arguments.get("reference", "")
        contracts = load_cached_contracts()

        for contract in contracts:
            if contract.get("referenceNumber-numeroReference") == reference or contract.get("solicitationNumber-numeroSollicitation") == reference:
                return [TextContent(type="text", text=json.dumps(contract, indent=2))]

        return [TextContent(type="text", text=f"Contract not found: {reference}")]

    elif name == "list_upcoming_deadlines":
        contracts = load_cached_contracts()
        if not contracts:
            contracts = fetch_all_contracts()
            save_contracts(contracts)

        days = arguments.get("days", 30)
        province = arguments.get("province", "").upper()
        now = datetime.now(timezone.utc)

        upcoming = []
        for contract in contracts:
            closing = parse_date(contract.get("tenderClosingDate-appelOffresDateCloture", ""))
            if not closing:
                continue

            if closing.tzinfo is None:
                closing = closing.replace(tzinfo=timezone.utc)

            days_until = (closing - now).days
            if 0 <= days_until <= days:
                region = contract.get("regionDelivery-regionLivraison-eng", "").upper()
                if province and province not in region:
                    continue

                upcoming.append({
                    "reference": contract.get("referenceNumber-numeroReference", "N/A"),
                    "title": contract.get("title-titre-eng", "N/A")[:80],
                    "closing_date": contract.get("tenderClosingDate-appelOffresDateCloture", "N/A"),
                    "days_until": days_until,
                    "region": region
                })

        upcoming.sort(key=lambda x: x["days_until"])
        return [TextContent(type="text", text=json.dumps(upcoming[:20], indent=2))]

    elif name == "refresh_data":
        contracts = fetch_all_contracts()
        save_contracts(contracts)
        return [TextContent(type="text", text=f"Refreshed data: {len(contracts)} contracts loaded")]

    elif name == "summarize_contracts":
        contracts = load_cached_contracts()
        if not contracts:
            contracts = fetch_all_contracts()
            save_contracts(contracts)

        summary = {
            "total_contracts": len(contracts),
            "sample": [
                {
                    "title": c.get("title-titre-eng", "N/A")[:60],
                    "closing": c.get("tenderClosingDate-appelOffresDateCloture", "N/A"),
                    "reference": c.get("referenceNumber-numeroReference", "N/A")
                }
                for c in contracts[:5]
            ]
        }
        return [TextContent(type="text", text=json.dumps(summary, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ============================================================
# SSE TRANSPORT SETUP
# ============================================================

sse = SseServerTransport("/messages/")


async def handle_sse(request):
    """Handle SSE connection."""
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


async def handle_messages(request):
    """Handle message posting."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "server": "canadabuys-mcp"})


# Starlette app with SSE routes
app = Starlette(
    debug=True,
    routes=[
        Route("/health", health),
        Route("/sse", handle_sse),
        Route("/messages/", handle_messages, methods=["POST"]),
    ],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
