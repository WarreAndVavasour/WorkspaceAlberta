#!/usr/bin/env python3
"""
Local Contacts MCP Server

Reads customer and supplier contacts from local Excel/CSV spreadsheets.
Small businesses often keep contact lists in spreadsheets - this MCP server
makes that data accessible to Claude agents.

Usage:
    python -m mcp_servers.local_contacts.server

Environment Variables:
    CONTACTS_FOLDER: Root folder containing contact spreadsheets
                     (default: ~/Documents/Contacts)
"""

import asyncio
import json
import os
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

# Data processing imports
try:
    import pandas as pd
except ImportError:
    pd = None
    print("Warning: pandas not installed. Excel support disabled.", file=sys.stderr)


def get_contacts_folder() -> Path:
    """Get the contacts folder from environment or default."""
    folder = os.environ.get("CONTACTS_FOLDER", "~/Documents/Contacts")
    return Path(folder).expanduser()


def find_spreadsheets(folder: Path) -> list[Path]:
    """Find all Excel and CSV files in folder."""
    if not folder.exists():
        return []

    files = []
    for pattern in ["*.xlsx", "*.xls", "*.csv"]:
        files.extend(folder.glob(pattern))
        files.extend(folder.glob(f"**/{pattern}"))  # Recursive

    return sorted(set(files))


def read_spreadsheet(file_path: Path) -> pd.DataFrame:
    """Read a spreadsheet file into a DataFrame."""
    if pd is None:
        raise ImportError("pandas is required for spreadsheet reading")

    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path, encoding="utf-8-sig")
    elif suffix in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def search_dataframe(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Search all text columns in a DataFrame for a query string."""
    # Convert all columns to string and search case-insensitively
    mask = df.astype(str).apply(
        lambda col: col.str.contains(query, case=False, na=False)
    ).any(axis=1)

    return df[mask]


def df_to_records(df: pd.DataFrame, source_file: str = None) -> list[dict]:
    """Convert DataFrame to list of dicts, adding source file info."""
    records = df.to_dict(orient="records")

    if source_file:
        for record in records:
            record["_source_file"] = source_file

    # Clean up NaN values
    for record in records:
        for key, value in list(record.items()):
            if pd.isna(value):
                record[key] = None

    return records


# Create MCP server
server = Server("local-contacts")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_contact_files",
            description="List all contact spreadsheets (Excel/CSV) in the contacts folder",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Folder to search (default: CONTACTS_FOLDER env var or ~/Documents/Contacts)"
                    }
                }
            }
        ),
        Tool(
            name="get_contact_columns",
            description="Get column names from a contact spreadsheet to understand its structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the spreadsheet file"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="search_contacts",
            description="Search for contacts matching a query across all spreadsheets",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to find in contact data (name, company, email, etc.)"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Specific file to search (optional, searches all if not provided)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_all_contacts",
            description="Get all contacts from a specific spreadsheet",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the spreadsheet file"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)",
                        "default": 100
                    }
                },
                "required": ["file_path"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_contact_files":
        folder_path = arguments.get("folder_path")
        folder = Path(folder_path).expanduser() if folder_path else get_contacts_folder()

        files = find_spreadsheets(folder)

        result = []
        for f in files:
            try:
                size_kb = f.stat().st_size // 1024
                result.append({
                    "path": str(f),
                    "name": f.name,
                    "size_kb": size_kb
                })
            except OSError:
                continue

        return [TextContent(
            type="text",
            text=json.dumps({
                "folder": str(folder),
                "file_count": len(result),
                "files": result
            }, indent=2)
        )]

    elif name == "get_contact_columns":
        file_path = Path(arguments["file_path"]).expanduser()

        if not file_path.exists():
            return [TextContent(type="text", text=json.dumps({"error": f"File not found: {file_path}"}))]

        try:
            df = read_spreadsheet(file_path)
            columns = list(df.columns)
            sample_row = df.head(1).to_dict(orient="records")[0] if len(df) > 0 else {}

            return [TextContent(
                type="text",
                text=json.dumps({
                    "file": str(file_path),
                    "row_count": len(df),
                    "columns": columns,
                    "sample_row": sample_row
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    elif name == "search_contacts":
        query = arguments["query"]
        file_path = arguments.get("file_path")
        max_results = arguments.get("max_results", 50)

        if file_path:
            files = [Path(file_path).expanduser()]
        else:
            files = find_spreadsheets(get_contacts_folder())

        all_results = []

        for f in files:
            try:
                df = read_spreadsheet(f)
                matches = search_dataframe(df, query)
                records = df_to_records(matches, str(f))
                all_results.extend(records)

                if len(all_results) >= max_results:
                    break
            except Exception as e:
                print(f"Error reading {f}: {e}", file=sys.stderr)
                continue

        # Limit results
        all_results = all_results[:max_results]

        return [TextContent(
            type="text",
            text=json.dumps({
                "query": query,
                "result_count": len(all_results),
                "results": all_results
            }, indent=2, default=str)
        )]

    elif name == "get_all_contacts":
        file_path = Path(arguments["file_path"]).expanduser()
        max_results = arguments.get("max_results", 100)

        if not file_path.exists():
            return [TextContent(type="text", text=json.dumps({"error": f"File not found: {file_path}"}))]

        try:
            df = read_spreadsheet(file_path)
            df = df.head(max_results)
            records = df_to_records(df, str(file_path))

            return [TextContent(
                type="text",
                text=json.dumps({
                    "file": str(file_path),
                    "row_count": len(records),
                    "contacts": records
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    else:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
