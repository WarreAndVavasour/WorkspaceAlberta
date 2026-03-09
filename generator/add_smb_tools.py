#!/usr/bin/env python3
"""Add SMB Foundation and Alberta-specific tools to catalog.json"""

import json
from pathlib import Path

# New SMB Foundation tools
NEW_TOOLS = [
    {
        "_comment": "=== SMB FOUNDATION TOOLS ===",
        "id": "filesystem",
        "display_name": "Local Filesystem",
        "category": "SMB Foundation",
        "description": "Read and write local files - contacts, invoices, quotes stored on your computer",
        "integration_status": "native",
        "mcp": {
            "server_name": "filesystem",
            "type": "node",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "${WORKSPACE_PATH}"],
            "env_vars": [
                {"name": "WORKSPACE_PATH", "description": "Root folder for file access (e.g., C:/Users/YourName/Documents)"}
            ]
        }
    },
    {
        "id": "gmail",
        "display_name": "Gmail",
        "category": "SMB Foundation",
        "description": "Email communication with customers and suppliers",
        "integration_status": "native",
        "mcp": {
            "server_name": "gmail",
            "type": "node",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-gmail"],
            "env_vars": [
                {"name": "GOOGLE_CREDENTIALS_JSON", "description": "OAuth credentials JSON for Gmail access"},
                {"name": "GOOGLE_TOKEN_JSON", "description": "OAuth token JSON for your Google account"}
            ]
        }
    },
    {
        "id": "google_calendar",
        "display_name": "Google Calendar",
        "category": "SMB Foundation",
        "description": "Appointments, job scheduling, and availability",
        "integration_status": "native",
        "mcp": {
            "server_name": "google-calendar",
            "type": "node",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-google-calendar"],
            "env_vars": [
                {"name": "GOOGLE_CREDENTIALS_JSON", "description": "OAuth credentials JSON"},
                {"name": "GOOGLE_TOKEN_JSON", "description": "OAuth token JSON"}
            ]
        }
    },
    {
        "id": "claude_code_agent",
        "display_name": "Claude Code Agent",
        "category": "SMB Foundation",
        "description": "AI coding assistant for automation and problem-solving",
        "integration_status": "native",
        "mcp": {
            "server_name": "claude-code",
            "type": "node",
            "command": "claude",
            "args": ["--mcp"],
            "env_vars": [
                {"name": "ANTHROPIC_API_KEY", "description": "Anthropic API key for Claude"}
            ]
        }
    },
    {
        "id": "e2b_sandbox",
        "display_name": "E2B Sandbox",
        "category": "SMB Foundation",
        "description": "Spawn isolated cloud environments for specialized agent tasks",
        "integration_status": "native",
        "mcp": {
            "server_name": "e2b",
            "type": "node",
            "command": "uvx",
            "args": ["e2b-mcp-server"],
            "env_vars": [
                {"name": "E2B_API_KEY", "description": "E2B API key for sandbox creation"}
            ]
        }
    },
    {
        "id": "web_search",
        "display_name": "Web Search",
        "category": "SMB Foundation",
        "description": "Search the web for information, competitors, suppliers",
        "integration_status": "native",
        "mcp": {
            "server_name": "brave-search",
            "type": "node",
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-brave-search"],
            "env_vars": [
                {"name": "BRAVE_API_KEY", "description": "Brave Search API key"}
            ]
        }
    },
    {
        "_comment": "=== CUSTOM ALBERTA TOOLS ===",
        "id": "local_contacts",
        "display_name": "Local Contacts",
        "category": "Custom / Alberta",
        "description": "Read customer and supplier contacts from local Excel/CSV files",
        "integration_status": "native",
        "mcp": {
            "server_name": "local-contacts",
            "type": "python",
            "command": "python",
            "args": ["-m", "mcp_servers.local_contacts.server"],
            "env_vars": [
                {"name": "CONTACTS_FOLDER", "description": "Folder containing contact spreadsheets (default: ~/Documents/Contacts)"}
            ]
        }
    },
    {
        "id": "canadabuys",
        "display_name": "CanadaBuys",
        "category": "Custom / Alberta",
        "description": "Search federal government procurement opportunities matching your industry",
        "integration_status": "native",
        "mcp": {
            "server_name": "canadabuys",
            "type": "python",
            "command": "python",
            "args": ["-m", "mcp_servers.canadabuys.server"],
            "env_vars": []
        }
    },
    {
        "id": "alberta_procurement",
        "display_name": "Alberta Procurement",
        "category": "Custom / Alberta",
        "description": "Search provincial government procurement opportunities",
        "integration_status": "native",
        "mcp": {
            "server_name": "alberta-procurement",
            "type": "python",
            "command": "python",
            "args": ["-m", "mcp_servers.alberta_procurement.server"],
            "env_vars": []
        }
    },
    {
        "id": "bid_calculator",
        "display_name": "Bid Calculator",
        "category": "Custom / Alberta",
        "description": "Estimate project costs and generate quotes for tender bids",
        "integration_status": "native",
        "mcp": {
            "server_name": "bid-calculator",
            "type": "python",
            "command": "python",
            "args": ["-m", "mcp_servers.bid_calculator.server"],
            "env_vars": [
                {"name": "PRICING_SHEET_PATH", "description": "Path to your materials/labor pricing spreadsheet"}
            ]
        }
    },
    {
        "id": "wave_accounting",
        "display_name": "Wave Accounting",
        "category": "Custom / Alberta",
        "description": "Free accounting software popular with small businesses",
        "integration_status": "proxy",
        "mcp": {
            "server_name": "wave",
            "type": "http_openapi",
            "openapi_url_env": "WAVE_OPENAPI_URL",
            "env_vars": [
                {"name": "WAVE_API_TOKEN", "description": "Wave API token"},
                {"name": "WAVE_BUSINESS_ID", "description": "Your Wave business ID"},
                {"name": "WAVE_OPENAPI_URL", "description": "OpenAPI spec URL for Wave (GraphQL wrapper)"}
            ]
        }
    },
    {
        "id": "jobber",
        "display_name": "Jobber",
        "category": "Custom / Alberta",
        "description": "Field service management for trades - scheduling, invoicing, CRM",
        "integration_status": "proxy",
        "mcp": {
            "server_name": "jobber",
            "type": "http_openapi",
            "openapi_url_env": "JOBBER_OPENAPI_URL",
            "env_vars": [
                {"name": "JOBBER_API_KEY", "description": "Jobber API key"},
                {"name": "JOBBER_OPENAPI_URL", "description": "OpenAPI spec URL for Jobber"}
            ]
        }
    },
    {
        "id": "inventory_tracker",
        "display_name": "Inventory Tracker",
        "category": "Custom / Alberta",
        "description": "Track equipment, materials, and stock from local spreadsheets",
        "integration_status": "native",
        "mcp": {
            "server_name": "inventory-tracker",
            "type": "python",
            "command": "python",
            "args": ["-m", "mcp_servers.inventory_tracker.server"],
            "env_vars": [
                {"name": "INVENTORY_SHEET_PATH", "description": "Path to inventory spreadsheet"}
            ]
        }
    }
]


def main():
    catalog_path = Path(__file__).parent / "catalog.json"

    # Read existing catalog
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    existing_ids = {tool["id"] for tool in catalog}

    # Add new tools (skip if already exists)
    added = 0
    for tool in NEW_TOOLS:
        if tool["id"] not in existing_ids:
            catalog.append(tool)
            added += 1
            print(f"  Added: {tool['id']} ({tool['display_name']})")
        else:
            print(f"  Skipped (exists): {tool['id']}")

    # Write back
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"\nAdded {added} new tools. Total: {len(catalog)} tools")


if __name__ == "__main__":
    main()
