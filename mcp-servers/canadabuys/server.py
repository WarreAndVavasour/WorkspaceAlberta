#!/usr/bin/env python3
"""
CanadaBuys MCP Server

Exposes federal contract data to AI assistants via Model Context Protocol.
Designed for Alberta's Steel, Lumber, and Aluminum industries.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import pipeline functions
from pipelines.canadabuys.pipeline import (
    load_config,
    build_code_rules,
    match_regions,
    match_keywords,
    match_unspsc,
    extract_unspsc_codes,
    parse_date,
    open_source,
    resolve_source,
    render_project_markdown,
)

# Initialize server
server = Server("canadabuys")

# Load config once at startup
CONFIG_PATH = Path(__file__).resolve().parents[2] / "pipelines" / "canadabuys" / "config.json"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "canadabuys"


def get_config() -> dict:
    """Load the CanadaBuys configuration."""
    if CONFIG_PATH.exists():
        return load_config(CONFIG_PATH)
    return {}


def get_cached_data() -> list[dict]:
    """Load the latest filtered contracts from cache."""
    latest_csv = OUTPUT_DIR / "latest.csv"
    if not latest_csv.exists():
        return []

    import csv
    with latest_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available CanadaBuys tools."""
    return [
        Tool(
            name="search_contracts",
            description="Search federal government contracts from CanadaBuys. Filter by industry (steel, lumber, aluminum), keywords, or region. Returns matching tender opportunities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "industry": {
                        "type": "string",
                        "description": "Filter by industry: steel, lumber, aluminum, or 'all'",
                        "enum": ["steel", "lumber", "aluminum", "all"]
                    },
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords (e.g., 'fabrication', 'structural', 'plywood')"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: open, closed, or all",
                        "enum": ["open", "closed", "all"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_contract_details",
            description="Get full details of a specific contract by reference number or solicitation number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference number or solicitation number of the contract"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_upcoming_deadlines",
            description="List contracts with upcoming closing deadlines, sorted by date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show contracts closing within this many days (default 30)",
                        "default": 30
                    },
                    "industry": {
                        "type": "string",
                        "description": "Filter by industry: steel, lumber, aluminum, or 'all'",
                        "enum": ["steel", "lumber", "aluminum", "all"]
                    }
                }
            }
        ),
        Tool(
            name="summarize_opportunities",
            description="Get a summary of current contract opportunities by industry and category.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="refresh_data",
            description="Refresh the contract data from CanadaBuys. Use sparingly - data is updated daily.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Data source: 'open' for all open tenders, 'new' for recent additions",
                        "enum": ["open", "new"],
                        "default": "open"
                    }
                }
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "search_contracts":
        return await search_contracts(arguments)
    elif name == "get_contract_details":
        return await get_contract_details(arguments)
    elif name == "list_upcoming_deadlines":
        return await list_upcoming_deadlines(arguments)
    elif name == "summarize_opportunities":
        return await summarize_opportunities(arguments)
    elif name == "refresh_data":
        return await refresh_data(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def search_contracts(args: dict) -> list[TextContent]:
    """Search contracts by industry, keywords, or status."""
    contracts = get_cached_data()
    if not contracts:
        return [TextContent(type="text", text="No contract data available. Run 'refresh_data' first.")]

    industry = args.get("industry", "all")
    keywords = args.get("keywords", "").lower()
    status = args.get("status", "all")
    limit = args.get("limit", 10)

    results = []
    for contract in contracts:
        # Filter by industry
        if industry != "all":
            match_industries = contract.get("match_industries", "").lower()
            if industry not in match_industries:
                continue

        # Filter by keywords
        if keywords:
            text = f"{contract.get('title-titre-eng', '')} {contract.get('tenderDescription-descriptionAppelOffres-eng', '')}".lower()
            if keywords not in text:
                continue

        # Filter by status
        if status != "all":
            contract_status = contract.get("tenderStatus-appelOffresStatut-eng", "").lower()
            if status == "open" and "open" not in contract_status:
                continue
            if status == "closed" and "closed" not in contract_status:
                continue

        results.append(contract)
        if len(results) >= limit:
            break

    if not results:
        return [TextContent(type="text", text="No contracts found matching your criteria.")]

    # Format results
    output = f"Found {len(results)} contracts:\n\n"
    for i, c in enumerate(results, 1):
        output += f"**{i}. {c.get('title-titre-eng', 'Untitled')}**\n"
        output += f"   Reference: {c.get('referenceNumber-numeroReference', 'N/A')}\n"
        output += f"   Status: {c.get('tenderStatus-appelOffresStatut-eng', 'N/A')}\n"
        output += f"   Closing: {c.get('tenderClosingDate-appelOffresDateCloture', 'N/A')}\n"
        output += f"   Industry: {c.get('match_industries', 'N/A')}\n"
        output += f"   Entity: {c.get('contractingEntityName-nomEntitContractante-eng', 'N/A')}\n\n"

    return [TextContent(type="text", text=output)]


async def get_contract_details(args: dict) -> list[TextContent]:
    """Get detailed information about a specific contract."""
    reference = args.get("reference", "")
    if not reference:
        return [TextContent(type="text", text="Please provide a reference number.")]

    contracts = get_cached_data()
    reference_lower = reference.lower()

    for contract in contracts:
        ref_num = contract.get("referenceNumber-numeroReference", "").lower()
        sol_num = contract.get("solicitationNumber-numeroSollicitation", "").lower()

        if reference_lower in ref_num or reference_lower in sol_num:
            # Return full markdown rendering
            markdown = render_project_markdown(contract)
            return [TextContent(type="text", text=markdown)]

    return [TextContent(type="text", text=f"Contract not found: {reference}")]


async def list_upcoming_deadlines(args: dict) -> list[TextContent]:
    """List contracts with upcoming deadlines."""
    days = args.get("days", 30)
    industry = args.get("industry", "all")

    contracts = get_cached_data()
    if not contracts:
        return [TextContent(type="text", text="No contract data available. Run 'refresh_data' first.")]

    now = datetime.utcnow()
    upcoming = []

    for contract in contracts:
        # Filter by industry
        if industry != "all":
            match_industries = contract.get("match_industries", "").lower()
            if industry not in match_industries:
                continue

        # Check closing date
        closing_str = contract.get("tenderClosingDate-appelOffresDateCloture", "")
        closing_date = parse_date(closing_str)

        if closing_date and closing_date > now:
            days_until = (closing_date - now).days
            if days_until <= days:
                upcoming.append((days_until, contract))

    # Sort by days until deadline
    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return [TextContent(type="text", text=f"No contracts closing within {days} days.")]

    output = f"Contracts closing within {days} days:\n\n"
    for days_until, c in upcoming[:20]:
        output += f"**{c.get('title-titre-eng', 'Untitled')}**\n"
        output += f"   Closes in: {days_until} days ({c.get('tenderClosingDate-appelOffresDateCloture', '')})\n"
        output += f"   Reference: {c.get('referenceNumber-numeroReference', 'N/A')}\n"
        output += f"   Industry: {c.get('match_industries', 'N/A')}\n\n"

    return [TextContent(type="text", text=output)]


async def summarize_opportunities(args: dict) -> list[TextContent]:
    """Summarize current contract opportunities."""
    contracts = get_cached_data()
    if not contracts:
        return [TextContent(type="text", text="No contract data available. Run 'refresh_data' first.")]

    # Count by industry
    industry_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    total_value = 0

    for contract in contracts:
        industries = contract.get("match_industries", "").split(";")
        for ind in industries:
            ind = ind.strip()
            if ind:
                industry_counts[ind] = industry_counts.get(ind, 0) + 1

        status = contract.get("tenderStatus-appelOffresStatut-eng", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    output = f"# CanadaBuys Contract Summary\n\n"
    output += f"**Total Contracts:** {len(contracts)}\n\n"

    output += "## By Industry\n"
    for industry, count in sorted(industry_counts.items(), key=lambda x: -x[1]):
        output += f"- {industry.title()}: {count}\n"

    output += "\n## By Status\n"
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        output += f"- {status}: {count}\n"

    # Get latest summary JSON if available
    summary_path = OUTPUT_DIR / "latest.json"
    if summary_path.exists():
        with summary_path.open("r") as f:
            summary = json.load(f)
            output += f"\n## Data Info\n"
            output += f"- Generated: {summary.get('generated_at_utc', 'Unknown')}\n"
            output += f"- Source: {summary.get('source', 'Unknown')}\n"

    return [TextContent(type="text", text=output)]


async def refresh_data(args: dict) -> list[TextContent]:
    """Refresh contract data from CanadaBuys."""
    source = args.get("source", "open")

    try:
        from pipelines.canadabuys.pipeline import run_pipeline

        csv_path, json_path = run_pipeline(
            config_path=CONFIG_PATH,
            source=source,
            output_dir=str(OUTPUT_DIR),
            max_rows=None,
            check_attachments=False,
            attachment_check_limit=0,
            attachment_timeout=20,
            download_attachments=False,
            download_limit=0,
        )

        return [TextContent(
            type="text",
            text=f"Data refreshed successfully!\n\nOutput files:\n- {csv_path}\n- {json_path}"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error refreshing data: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
