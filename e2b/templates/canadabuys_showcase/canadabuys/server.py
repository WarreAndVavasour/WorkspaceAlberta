#!/usr/bin/env python3
"""
CanadaBuys MCP Server

Search Canadian federal government contracts via Model Context Protocol.
Filters available for province, industry keywords, and status.

Usage:
    uvx canadabuys-mcp

Configuration:
    CANADABUYS_DATA_DIR - Where to cache data (default: ~/.canadabuys/)
"""

import csv
import gzip
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Initialize server
server = Server("canadabuys")

# Configuration
DATA_DIR = Path(os.environ.get("CANADABUYS_DATA_DIR", Path.home() / ".canadabuys"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# CanadaBuys open data URLs
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

        # Decompress if gzipped
        if raw_data[:2] == b'\x1f\x8b':
            raw_data = gzip.decompress(raw_data)

        # Decode
        text_data = raw_data.decode("utf-8-sig")

        # Parse CSV - handle potential BOM and empty lines
        lines = [line for line in text_data.split('\n') if line.strip()]
        if not lines:
            return []

        reader = csv.DictReader(lines)
        return list(reader)


def save_contracts(contracts: list[dict]) -> Path:
    """Save contracts to local cache."""
    latest_path = DATA_DIR / "latest.csv"

    if not contracts:
        return latest_path

    # Filter out None keys
    fieldnames = [k for k in contracts[0].keys() if k is not None]

    with latest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(contracts)

    # Save summary
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_contracts": len(contracts),
    }
    with (DATA_DIR / "latest.json").open("w") as f:
        json.dump(summary, f, indent=2)

    return latest_path


def load_contracts() -> list[dict]:
    """Load contracts from local cache."""
    latest_path = DATA_DIR / "latest.csv"
    if not latest_path.exists():
        return []

    with latest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def get_field(contract: dict, *field_names: str) -> str:
    """Get first non-empty field value from contract."""
    for name in field_names:
        val = contract.get(name, "")
        if val:
            return str(val)
    return ""


# ============== Business Profile ==============

# Industry keywords for matching (from pipeline config)
INDUSTRY_KEYWORDS = {
    "steel": ["steel", "stainless", "carbon steel", "structural steel", "metal fabrication",
              "welding", "iron", "metalwork", "rebar", "girder", "beam"],
    "lumber": ["lumber", "wood", "timber", "forestry", "plywood", "sawmill", "log",
               "pulp", "paper", "woodwork", "carpentry", "framing"],
    "aluminum": ["aluminum", "aluminium", "bauxite", "smelting", "extrusion"],
    "construction": ["construction", "building", "demolition", "renovation", "contractor",
                     "infrastructure", "excavation", "concrete", "masonry"],
}

# UNSPSC code prefixes by industry (from pipeline config)
INDUSTRY_UNSPSC = {
    "steel": ["111017", "301017", "111016", "232400", "251000", "221000", "301000"],
    "lumber": ["1112", "301515", "111215", "301524", "301521"],
    "aluminum": ["1111", "111106", "301116"],
    "construction": ["721", "301", "221", "251"],
}


def load_profile() -> dict:
    """Load business profile from disk."""
    profile_path = DATA_DIR / "profile.json"
    if not profile_path.exists():
        return {}
    with profile_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> None:
    """Save business profile to disk."""
    profile_path = DATA_DIR / "profile.json"
    with profile_path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def extract_keywords(description: str) -> list[str]:
    """Extract relevant keywords from business description."""
    if not description:
        return []

    desc_lower = description.lower()
    found = []

    # Check for industry keywords
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower and kw not in found:
                found.append(kw)

    # Also extract significant words (nouns likely to appear in contracts)
    words = re.findall(r'\b[a-z]{4,}\b', desc_lower)
    for word in words:
        if word not in found and word not in ["that", "this", "with", "from", "have", "been", "will", "your", "they", "their", "about", "which", "would", "could", "should", "these", "those", "other", "some", "into", "also", "make", "made"]:
            found.append(word)

    return found[:20]  # Limit to 20 keywords


def infer_industries(keywords: list[str], description: str = "") -> list[str]:
    """Infer which industries match based on keywords."""
    industries = set()
    text = " ".join(keywords) + " " + description.lower()

    for industry, kw_list in INDUSTRY_KEYWORDS.items():
        for kw in kw_list:
            if kw in text:
                industries.add(industry)
                break

    return list(industries)


def score_contract(contract: dict, profile: dict) -> tuple[int, list[str]]:
    """Score a contract against a business profile. Returns (score, reasons)."""
    score = 0
    reasons = []

    keywords = profile.get("capabilities", [])
    industries = profile.get("industries", [])
    location = profile.get("location", "").lower()

    title = get_field(contract, "title-titre-eng", "title-titre-fra").lower()
    desc = get_field(contract, "tenderDescription-descriptionAppelOffres-eng").lower()
    regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
    unspsc = get_field(contract, "unspsc", "")

    # Keyword matches in title (high value)
    title_matches = [kw for kw in keywords if kw.lower() in title]
    if title_matches:
        score += 10 * len(title_matches)
        reasons.append(f"title matches: {', '.join(title_matches[:3])}")

    # Keyword matches in description
    desc_matches = [kw for kw in keywords if kw.lower() in desc and kw.lower() not in title]
    if desc_matches:
        score += 5 * len(desc_matches)
        reasons.append(f"description matches: {', '.join(desc_matches[:3])}")

    # UNSPSC code matches
    for industry in industries:
        prefixes = INDUSTRY_UNSPSC.get(industry, [])
        for prefix in prefixes:
            if prefix in unspsc:
                score += 15
                reasons.append(f"UNSPSC code matches {industry}")
                break

    # Region match
    if location:
        # Extract province/city from location
        loc_parts = [p.strip().lower() for p in location.replace(",", " ").split()]
        for part in loc_parts:
            if len(part) > 3 and part in regions:
                score += 10
                reasons.append(f"delivers to {part}")
                break

    # Closing soon bonus (urgency)
    closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
    closing_date = parse_date(closing_str)
    if closing_date:
        now = datetime.now(timezone.utc)
        if closing_date.tzinfo is None:
            closing_date = closing_date.replace(tzinfo=timezone.utc)
        days_until = (closing_date - now).days
        if 0 < days_until <= 14:
            score += 5
            reasons.append(f"closes in {days_until} days")

    return score, reasons


def render_contract_markdown(contract: dict) -> str:
    """Render a contract as markdown."""
    title = get_field(contract, "title-titre-eng", "title-titre-fra", "Title")
    if not title:
        title = "Untitled Contract"

    lines = [f"# {title}", ""]

    lines.append("## Overview")
    lines.append(f"- **Reference:** {get_field(contract, 'referenceNumber-numeroReference', 'Reference Number')}")
    lines.append(f"- **Solicitation:** {get_field(contract, 'solicitationNumber-numeroSollicitation', 'Solicitation Number')}")
    lines.append(f"- **Status:** {get_field(contract, 'tenderStatus-appelOffresStatut-eng', 'Status')}")
    lines.append(f"- **Closing Date:** {get_field(contract, 'tenderClosingDate-appelOffresDateCloture', 'Closing Date')}")
    lines.append(f"- **Entity:** {get_field(contract, 'contractingEntityName-nomEntitContractante-eng', 'Organization')}")
    lines.append("")

    lines.append("## Regions")
    lines.append(f"- **Opportunity:** {get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng', 'Regions')}")
    lines.append(f"- **Delivery:** {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}")
    lines.append("")

    desc = get_field(contract, "tenderDescription-descriptionAppelOffres-eng", "Description")
    if desc:
        lines.append("## Description")
        lines.append(desc[:2000])
        lines.append("")

    notice_url = get_field(contract, "noticeURL-URLavis-eng", "URL")
    if notice_url:
        lines.append("## Links")
        lines.append(f"- [View on CanadaBuys]({notice_url})")

    return "\n".join(lines)


# ============== MCP Tools ==============

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_contracts",
            description="Search Canadian federal government contracts. Filter by keywords, province, or status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "Search keywords (e.g., 'steel', 'construction', 'IT services')"
                    },
                    "province": {
                        "type": "string",
                        "description": "Filter by province (e.g., 'Alberta', 'Ontario', 'Quebec')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 10)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="get_contract_details",
            description="Get full details of a contract by reference or solicitation number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Reference or solicitation number"
                    }
                },
                "required": ["reference"]
            }
        ),
        Tool(
            name="list_upcoming_deadlines",
            description="List contracts with upcoming closing deadlines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Show contracts closing within N days (default 30)",
                        "default": 30
                    },
                    "province": {
                        "type": "string",
                        "description": "Filter by province"
                    }
                }
            }
        ),
        Tool(
            name="summarize_contracts",
            description="Get a summary of available contracts.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="refresh_data",
            description="Refresh contract data from CanadaBuys.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # ===== Business Profile Tools =====
        Tool(
            name="set_business_profile",
            description="Tell me about your business. I'll save your profile and use it to find matching government contracts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Your company name"
                    },
                    "location": {
                        "type": "string",
                        "description": "Where you're located (e.g., 'Edmonton, Alberta')"
                    },
                    "description": {
                        "type": "string",
                        "description": "What does your business do? Describe your products, services, and capabilities."
                    }
                },
                "required": ["description"]
            }
        ),
        Tool(
            name="find_opportunities",
            description="Find government contracts that match your business profile. Returns scored and ranked opportunities with explanations of why each one fits your capabilities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Only show contracts closing within N days (default: 60)",
                        "default": 60
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum opportunities to return (default: 15)",
                        "default": 15
                    }
                }
            }
        ),
        Tool(
            name="get_my_profile",
            description="View your current business profile that's being used to match contracts.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "search_contracts":
            return await search_contracts(arguments)
        elif name == "get_contract_details":
            return await get_contract_details(arguments)
        elif name == "list_upcoming_deadlines":
            return await list_upcoming_deadlines(arguments)
        elif name == "summarize_contracts":
            return await summarize_contracts(arguments)
        elif name == "refresh_data":
            return await refresh_data(arguments)
        # Business Profile Tools
        elif name == "set_business_profile":
            return await set_business_profile(arguments)
        elif name == "find_opportunities":
            return await find_opportunities(arguments)
        elif name == "get_my_profile":
            return await get_my_profile(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def search_contracts(args: dict) -> list[TextContent]:
    """Search contracts."""
    contracts = load_contracts()
    if not contracts:
        return [TextContent(type="text", text="No data available. Run 'refresh_data' first.")]

    keywords = args.get("keywords", "").lower()
    province = args.get("province", "").lower()
    limit = args.get("limit", 10)

    results = []
    for contract in contracts:
        # Keyword filter
        if keywords:
            text = f"{get_field(contract, 'title-titre-eng')} {get_field(contract, 'tenderDescription-descriptionAppelOffres-eng')}".lower()
            if keywords not in text:
                continue

        # Province filter
        if province:
            regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
            if province not in regions:
                continue

        results.append(contract)
        if len(results) >= limit:
            break

    if not results:
        return [TextContent(type="text", text="No contracts found matching criteria.")]

    output = f"Found {len(results)} contracts:\n\n"
    for i, c in enumerate(results, 1):
        title = get_field(c, "title-titre-eng", "title-titre-fra")[:60]
        output += f"**{i}. {title}**\n"
        output += f"   Reference: {get_field(c, 'referenceNumber-numeroReference')}\n"
        output += f"   Closing: {get_field(c, 'tenderClosingDate-appelOffresDateCloture')}\n"
        output += f"   Entity: {get_field(c, 'contractingEntityName-nomEntitContractante-eng')}\n\n"

    return [TextContent(type="text", text=output)]


async def get_contract_details(args: dict) -> list[TextContent]:
    """Get contract details."""
    reference = args.get("reference", "").lower()
    if not reference:
        return [TextContent(type="text", text="Please provide a reference number.")]

    contracts = load_contracts()

    for contract in contracts:
        ref = get_field(contract, "referenceNumber-numeroReference").lower()
        sol = get_field(contract, "solicitationNumber-numeroSollicitation").lower()

        if reference in ref or reference in sol:
            return [TextContent(type="text", text=render_contract_markdown(contract))]

    return [TextContent(type="text", text=f"Contract not found: {reference}")]


async def list_upcoming_deadlines(args: dict) -> list[TextContent]:
    """List upcoming deadlines."""
    days = args.get("days", 30)
    province = args.get("province", "").lower()

    contracts = load_contracts()
    if not contracts:
        return [TextContent(type="text", text="No data available. Run 'refresh_data' first.")]

    now = datetime.now(timezone.utc)
    upcoming = []

    for contract in contracts:
        if province:
            regions = f"{get_field(contract, 'regionsOfOpportunity-regionAppelOffres-eng')} {get_field(contract, 'regionsOfDelivery-regionsLivraison-eng')}".lower()
            if province not in regions:
                continue

        closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
        closing_date = parse_date(closing_str)

        if closing_date:
            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(tzinfo=timezone.utc)

            if closing_date > now:
                days_until = (closing_date - now).days
                if days_until <= days:
                    upcoming.append((days_until, contract))

    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return [TextContent(type="text", text=f"No contracts closing within {days} days.")]

    output = f"Contracts closing within {days} days:\n\n"
    for days_until, c in upcoming[:20]:
        title = get_field(c, "title-titre-eng")[:50]
        output += f"**{title}**\n"
        output += f"   Closes in: {days_until} days\n"
        output += f"   Reference: {get_field(c, 'referenceNumber-numeroReference')}\n\n"

    return [TextContent(type="text", text=output)]


async def summarize_contracts(args: dict) -> list[TextContent]:
    """Summarize available contracts."""
    contracts = load_contracts()
    if not contracts:
        return [TextContent(type="text", text="No data available. Run 'refresh_data' first.")]

    output = f"# CanadaBuys Contract Summary\n\n"
    output += f"**Total Contracts:** {len(contracts)}\n\n"

    # Sample some titles
    output += "## Sample Opportunities\n"
    for c in contracts[:5]:
        title = get_field(c, "title-titre-eng")[:60]
        output += f"- {title}\n"

    summary_path = DATA_DIR / "latest.json"
    if summary_path.exists():
        with summary_path.open("r") as f:
            summary = json.load(f)
            output += f"\n## Data Info\n"
            output += f"- Last Updated: {summary.get('generated_at_utc', 'Unknown')}\n"

    return [TextContent(type="text", text=output)]


async def refresh_data(args: dict) -> list[TextContent]:
    """Refresh data from CanadaBuys."""
    try:
        contracts = fetch_all_contracts()
        save_contracts(contracts)

        return [TextContent(
            type="text",
            text=f"Data refreshed!\n\n**Total Contracts:** {len(contracts)}"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============== Business Profile Handlers ==============

async def set_business_profile(args: dict) -> list[TextContent]:
    """Save business profile for smart matching."""
    description = args.get("description", "")
    if not description:
        return [TextContent(type="text", text="Please describe your business.")]

    # Extract keywords and infer industries
    capabilities = extract_keywords(description)
    industries = infer_industries(capabilities, description)

    profile = {
        "company_name": args.get("company_name", "My Business"),
        "location": args.get("location", ""),
        "description": description,
        "capabilities": capabilities,
        "industries": industries,
    }

    save_profile(profile)

    output = "# Profile Saved!\n\n"
    output += f"**Company:** {profile['company_name']}\n"
    if profile['location']:
        output += f"**Location:** {profile['location']}\n"
    output += f"\n**Detected Industries:** {', '.join(industries) if industries else 'General'}\n"
    output += f"**Keywords I'll search for:** {', '.join(capabilities[:10])}\n"
    output += "\nUse `find_opportunities` to see matching contracts!"

    return [TextContent(type="text", text=output)]


async def find_opportunities(args: dict) -> list[TextContent]:
    """Find contracts matching business profile."""
    profile = load_profile()
    if not profile:
        return [TextContent(type="text", text="No business profile set. Use `set_business_profile` first to tell me about your business.")]

    contracts = load_contracts()
    if not contracts:
        return [TextContent(type="text", text="No contract data available. Run `refresh_data` first.")]

    days = args.get("days", 60)
    limit = args.get("limit", 15)
    now = datetime.now(timezone.utc)

    # Score all contracts
    scored = []
    for contract in contracts:
        # Check if closing date is within range
        closing_str = get_field(contract, "tenderClosingDate-appelOffresDateCloture")
        closing_date = parse_date(closing_str)

        if closing_date:
            if closing_date.tzinfo is None:
                closing_date = closing_date.replace(tzinfo=timezone.utc)
            days_until = (closing_date - now).days

            if days_until < 0 or days_until > days:
                continue  # Skip expired or too far out

            score, reasons = score_contract(contract, profile)
            if score > 0:
                scored.append((score, days_until, contract, reasons))

    # Sort by score descending
    scored.sort(key=lambda x: -x[0])

    if not scored:
        return [TextContent(type="text", text=f"No matching opportunities found in the next {days} days.\n\nTry:\n- Updating your profile with more detail\n- Increasing the days parameter\n- Running `refresh_data` to get latest contracts")]

    company = profile.get("company_name", "Your Business")
    output = f"# Opportunities for {company}\n\n"
    output += f"Found **{len(scored)}** matching contracts (showing top {min(limit, len(scored))})\n\n"

    for i, (score, days_until, contract, reasons) in enumerate(scored[:limit], 1):
        title = get_field(contract, "title-titre-eng", "title-titre-fra")[:70]
        ref = get_field(contract, "referenceNumber-numeroReference")
        entity = get_field(contract, "contractingEntityName-nomEntitContractante-eng")[:40]

        output += f"### {i}. {title}\n"
        output += f"**Match Score:** {score} | **Closes in:** {days_until} days\n"
        output += f"**Why it matches:** {'; '.join(reasons)}\n"
        output += f"**Entity:** {entity}\n"
        output += f"**Reference:** `{ref}`\n\n"

    output += "---\n*Use `get_contract_details` with a reference number to see full details.*"

    return [TextContent(type="text", text=output)]


async def get_my_profile(args: dict) -> list[TextContent]:
    """Return current business profile."""
    profile = load_profile()
    if not profile:
        return [TextContent(type="text", text="No business profile set yet.\n\nUse `set_business_profile` to tell me about your business!")]

    output = "# Your Business Profile\n\n"
    output += f"**Company:** {profile.get('company_name', 'Not set')}\n"
    output += f"**Location:** {profile.get('location', 'Not set')}\n\n"
    output += f"**Description:**\n{profile.get('description', 'Not set')}\n\n"
    output += f"**Industries:** {', '.join(profile.get('industries', [])) or 'None detected'}\n"
    output += f"**Keywords:** {', '.join(profile.get('capabilities', [])[:15])}\n"

    return [TextContent(type="text", text=output)]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
