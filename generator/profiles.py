from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Literal

from .generator import BuildOptions, Tool, build_mcp_json, load_catalog, select_tools


FOUNDATION_TOOLS = [
    "filesystem",
    "google_drive",
    "gmail",
    "google_calendar",
    "claude_code_agent",
    "e2b_sandbox",
    "web_search",
]

INDUSTRY_OVERLAYS: dict[str, list[str]] = {
    "steel_fabrication": [
        "canadabuys",
        "alberta_procurement",
        "local_contacts",
        "bid_calculator",
        "quickbooks_online",
    ],
    "lumber_mill": [
        "canadabuys",
        "alberta_procurement",
        "local_contacts",
        "inventory_tracker",
        "quickbooks_online",
    ],
    "trades_contractor": [
        "canadabuys",
        "alberta_procurement",
        "local_contacts",
        "jobber",
        "bid_calculator",
        "wave_accounting",
    ],
    "general_contractor": [
        "canadabuys",
        "alberta_procurement",
        "local_contacts",
        "bid_calculator",
        "quickbooks_online",
    ],
    "metal_fabrication": [
        "canadabuys",
        "alberta_procurement",
        "local_contacts",
        "bid_calculator",
        "inventory_tracker",
        "quickbooks_online",
    ],
    "equipment_rental": [
        "local_contacts",
        "inventory_tracker",
        "jobber",
        "quickbooks_online",
    ],
    "professional_services": [
        "local_contacts",
        "calendly",
        "quickbooks_online",
    ],
}


def get_profile_tool_ids(profile: str) -> list[str]:
    foundation = list(FOUNDATION_TOOLS)
    if profile == "foundation":
        return foundation

    overlay = INDUSTRY_OVERLAYS.get(profile)
    if overlay is None:
        raise ValueError(f"Unknown profile: {profile}")

    return list(dict.fromkeys(foundation + overlay))


def build_profile_mcp_json(
    profile: str, options: BuildOptions | None = None
) -> dict[str, object]:
    catalog = load_catalog()
    tool_ids = get_profile_tool_ids(profile)
    available_ids = {tool["id"] for tool in catalog}

    valid_ids = [tool_id for tool_id in tool_ids if tool_id in available_ids]
    missing_ids = [tool_id for tool_id in tool_ids if tool_id not in available_ids]

    if missing_ids:
        print(f"Warning: Missing tools in catalog: {', '.join(missing_ids)}", file=sys.stderr)

    tools = select_tools(catalog, valid_ids)
    return build_mcp_json(tools, options)


def get_profile_info(profile: str) -> dict[str, object]:
    tools = get_profile_tool_ids(profile)
    descriptions = {
        "foundation": "Core tools for any small business",
        "steel_fabrication": "Steel fabrication shops bidding on government contracts",
        "lumber_mill": "Lumber mills and wood product manufacturers",
        "trades_contractor": "Trades contractors (electricians, plumbers, HVAC)",
        "general_contractor": "General contractors managing construction projects",
        "metal_fabrication": "Metal fabrication and machining shops",
        "equipment_rental": "Equipment rental and sales businesses",
        "professional_services": "Professional services (consultants, accountants)",
    }

    return {
        "name": profile,
        "description": descriptions.get(profile, "Unknown profile"),
        "tool_count": len(tools),
        "tools": tools,
    }


def list_profiles() -> list[str]:
    return ["foundation", *INDUSTRY_OVERLAYS.keys()]


def generate_all_profiles(
    options: BuildOptions | None = None,
) -> dict[str, dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    for profile in list_profiles():
        try:
            profiles[profile] = build_profile_mcp_json(profile, options)
        except ValueError as exc:
            print(f"Error generating profile {profile}: {exc}", file=sys.stderr)

    return profiles


def _print_profile_list() -> None:
    print("\nAvailable Profiles:\n")
    for profile in list_profiles():
        info = get_profile_info(profile)
        print(f"  {profile}")
        print(f"    {info['description']}")
        print(f"    Tools ({info['tool_count']}): {', '.join(info['tools'])}\n")


def main(args: list[str]) -> int:
    if not args:
        print(
            """
Usage: python -m generator.profiles <command> [args]

Commands:
  list                    List all available profiles
  generate <profile>      Generate MCP config for a profile
  generate-all            Generate MCP configs for all profiles

Examples:
  python -m generator.profiles list
  python -m generator.profiles generate steel_fabrication
  python -m generator.profiles generate-all > profiles.json
""",
            file=sys.stderr,
        )
        return 1

    command = args[0]

    if command == "list":
        _print_profile_list()
        return 0

    if command == "generate":
        if len(args) < 2:
            print("Usage: python -m generator.profiles generate <profile_name>", file=sys.stderr)
            return 1
        profile = args[1]
        try:
            config = build_profile_mcp_json(profile)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(config, indent=2))
        return 0

    if command == "generate-all":
        profiles = generate_all_profiles()
        print(json.dumps(profiles, indent=2))
        return 0

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
