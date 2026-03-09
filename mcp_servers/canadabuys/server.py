#!/usr/bin/env python3
"""
CanadaBuys MCP Server

Wraps the existing CanadaBuys pipeline to provide MCP access to federal
government procurement opportunities. Searches are filtered by industry
(steel, lumber, construction, etc.) and region (Alberta).

Usage:
    python -m mcp_servers.canadabuys.server
"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Path to the pipelines directory
PIPELINES_DIR = Path(__file__).parents[2] / "pipelines" / "canadabuys"
OUTPUT_DIR = Path(__file__).parents[2] / "output" / "canadabuys"

# Add pipelines to path for imports
sys.path.insert(0, str(PIPELINES_DIR.parent.parent))


def get_available_industries() -> list[str]:
    """Get list of industries from the pipeline config."""
    config_path = PIPELINES_DIR / "config.json"
    if not config_path.exists():
        return ["steel", "lumber", "construction", "metals"]

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return list(config.get("industries", {}).keys())
    except Exception:
        return ["steel", "lumber", "construction", "metals"]


def read_latest_results() -> tuple[list[dict], dict]:
    """Read the latest pipeline results."""
    csv_path = OUTPUT_DIR / "latest.csv"
    json_path = OUTPUT_DIR / "latest.json"

    results = []
    summary = {}

    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            results = list(reader)

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

    return results, summary


def filter_results(
    results: list[dict],
    industries: list[str] = None,
    regions: list[str] = None,
    status: str = None,
    max_results: int = 20
) -> list[dict]:
    """Filter results by industry, region, and status."""
    filtered = results

    if industries:
        industries_lower = [i.lower() for i in industries]
        filtered = [
            r for r in filtered
            if any(ind in r.get("match_industries", "").lower() for ind in industries_lower)
        ]

    if regions:
        regions_lower = [r.lower() for r in regions]
        filtered = [
            r for r in filtered
            if any(reg in r.get("match_regions", "").lower() for reg in regions_lower)
        ]

    if status:
        filtered = [
            r for r in filtered
            if status.lower() in r.get("tenderStatus-appelOffresStatut-eng", "").lower()
        ]

    return filtered[:max_results]


def format_tender_summary(tender: dict) -> dict:
    """Format a tender for concise display."""
    return {
        "reference": tender.get("referenceNumber-numeroReference", ""),
        "title": tender.get("title-titre-eng", ""),
        "status": tender.get("tenderStatus-appelOffresStatut-eng", ""),
        "closing_date": tender.get("tenderClosingDate-appelOffresDateCloture", ""),
        "category": tender.get("procurementCategory-categorieApprovisionnement", ""),
        "entity": tender.get("contractingEntityName-nomEntitContractante-eng", ""),
        "regions": tender.get("regionsOfDelivery-regionsLivraison-eng", ""),
        "matched_industries": tender.get("match_industries", ""),
        "matched_codes": tender.get("match_codes", ""),
        "notice_url": tender.get("noticeURL-URLavis-eng", ""),
    }


# Create MCP server
server = Server("canadabuys")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    industries = get_available_industries()

    return [
        Tool(
            name="search_tenders",
            description=f"Search CanadaBuys for open government tenders matching your industry. Available industries: {', '.join(industries)}",
            inputSchema={
                "type": "object",
                "properties": {
                    "industries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"Filter by industry: {', '.join(industries)}"
                    },
                    "regions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by delivery region (default: Alberta)",
                        "default": ["Alberta"]
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by tender status (e.g., 'Open', 'Closed')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="get_tender_details",
            description="Get full details for a specific tender by reference number",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference_number": {
                        "type": "string",
                        "description": "The tender reference number"
                    }
                },
                "required": ["reference_number"]
            }
        ),
        Tool(
            name="get_pipeline_summary",
            description="Get summary statistics from the last pipeline run",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="run_pipeline",
            description="Run the CanadaBuys pipeline to fetch fresh data (may take a few minutes)",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum rows to process (default: 1000)",
                        "default": 1000
                    },
                    "check_attachments": {
                        "type": "boolean",
                        "description": "Check attachment URLs (slower but more complete)",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="list_industries",
            description="List available industries that can be searched",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "search_tenders":
        industries = arguments.get("industries")
        regions = arguments.get("regions", ["Alberta"])
        status = arguments.get("status")
        max_results = arguments.get("max_results", 20)

        results, summary = read_latest_results()

        if not results:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": "No results available. Run the pipeline first with run_pipeline tool.",
                    "hint": "The pipeline fetches data from CanadaBuys and filters for Alberta opportunities."
                }, indent=2)
            )]

        filtered = filter_results(results, industries, regions, status, max_results)
        formatted = [format_tender_summary(t) for t in filtered]

        return [TextContent(
            type="text",
            text=json.dumps({
                "query": {
                    "industries": industries,
                    "regions": regions,
                    "status": status
                },
                "result_count": len(formatted),
                "total_available": len(results),
                "tenders": formatted
            }, indent=2)
        )]

    elif name == "get_tender_details":
        reference = arguments["reference_number"]
        results, _ = read_latest_results()

        for tender in results:
            if tender.get("referenceNumber-numeroReference") == reference:
                return [TextContent(
                    type="text",
                    text=json.dumps(tender, indent=2)
                )]

        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Tender not found: {reference}"})
        )]

    elif name == "get_pipeline_summary":
        _, summary = read_latest_results()

        if not summary:
            return [TextContent(
                type="text",
                text=json.dumps({"error": "No pipeline summary available. Run the pipeline first."})
            )]

        return [TextContent(
            type="text",
            text=json.dumps(summary, indent=2)
        )]

    elif name == "run_pipeline":
        max_rows = arguments.get("max_rows", 1000)
        check_attachments = arguments.get("check_attachments", False)

        try:
            # Import and run the pipeline
            from pipelines.canadabuys.pipeline import run_pipeline as execute_pipeline

            config_path = PIPELINES_DIR / "config.json"
            csv_path, json_path = execute_pipeline(
                config_path=config_path,
                source="open",
                output_dir=str(OUTPUT_DIR),
                max_rows=max_rows,
                check_attachments=check_attachments,
                attachment_check_limit=0,
                attachment_timeout=20,
                download_attachments=False,
                download_limit=0,
            )

            # Read the new summary
            with open(json_path, "r", encoding="utf-8") as f:
                summary = json.load(f)

            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Pipeline completed. Found {summary.get('matched_total', 0)} matching tenders.",
                    "output_csv": str(csv_path),
                    "output_json": str(json_path),
                    "summary": summary
                }, indent=2)
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "error": str(e),
                    "hint": "Make sure the pipeline dependencies are installed and config.json exists."
                }, indent=2)
            )]

    elif name == "list_industries":
        industries = get_available_industries()

        return [TextContent(
            type="text",
            text=json.dumps({
                "industries": industries,
                "description": "These industries are configured in the pipeline. Each has UNSPSC codes and keywords for matching tenders."
            }, indent=2)
        )]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
