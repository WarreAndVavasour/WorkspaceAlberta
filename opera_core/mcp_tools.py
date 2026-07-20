"""MCP Tool definitions for the OPERA Cloud data-tap adapters.

This module declares the public tool surface — names, descriptions, and JSON
input schemas — shared by the OPERA MCP adapters. It contains no logic:
every tool name here must have a matching async handler in
``opera_core.service`` and appear in ``service.TOOL_NAMES``, or calls will
fail at dispatch.

All tools are read-only analytics over OPERA Cloud Reporting & Analytics
subject areas, plus a small local layer (CSV exports and synced tables) for
offline analysis. In mock mode every tool works offline against demo data.

When adding a tool: add the ``Tool`` entry here, implement the async handler
in ``opera_core/service.py``, add the name to ``TOOL_NAMES``, and cover it
in ``tests/``. Keep descriptions user-facing and concrete — they are what
the calling model sees when choosing tools.
"""

from mcp.types import Tool

_DATE_FILTER_PROPERTIES = {
    "date_field": {
        "type": "string",
        "description": "Name of the date filter input to apply (see describe_subject_area filters). Required when using start_date/end_date.",
    },
    "start_date": {
        "type": "string",
        "description": "Optional start date (YYYY-MM-DD) applied to date_field.",
    },
    "end_date": {
        "type": "string",
        "description": "Optional end date (YYYY-MM-DD) applied to date_field.",
    },
}


def get_mcp_tools() -> list[Tool]:
    """Return the full declared OPERA tool list in stable order."""
    return [
        Tool(
            name="opera_auth_status",
            description="Check OPERA Cloud configuration: whether settings are present, whether mock mode is on, and whether an OAuth token can be obtained. Never displays secrets.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_subject_areas",
            description="List available OPERA Reporting & Analytics subject areas (Financial, Statistics, Rates, Profiles, Bookings, and more) grouped by category.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="describe_subject_area",
            description="Show the fields, filter inputs, and an example GraphQL query for one OPERA subject area.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Subject area name from list_subject_areas",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="run_graphql_query",
            description="Run a raw read-only GraphQL query against OPERA R&A. Prefer query_subject_area for validated queries; use this for custom queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "GraphQL query text",
                    },
                    "variables": {
                        "type": "object",
                        "description": "Optional GraphQL variables as a JSON object",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_subject_area",
            description="Query an OPERA subject area safely: fields are validated against the catalog, dates filter the results, and the generated GraphQL is shown. Unknown fields are rejected with the valid list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_area": {
                        "type": "string",
                        "description": "Subject area name from list_subject_areas",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Field names to return (see describe_subject_area)",
                    },
                    **{
                        key: value
                        for key, value in _DATE_FILTER_PROPERTIES.items()
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows (default 100, max 1000)",
                        "default": 100,
                    },
                },
                "required": ["subject_area", "fields"],
            },
        ),
        Tool(
            name="export_to_csv",
            description="Query an OPERA subject area and save the rows to a local CSV file. Returns the file path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_area": {
                        "type": "string",
                        "description": "Subject area name from list_subject_areas",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Field names to export (see describe_subject_area)",
                    },
                    **{
                        key: value
                        for key, value in _DATE_FILTER_PROPERTIES.items()
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional export file name (default: <subject_area>_export)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows (default 100, max 1000)",
                        "default": 100,
                    },
                },
                "required": ["subject_area", "fields"],
            },
        ),
        Tool(
            name="sync_subject_area",
            description="Query an OPERA subject area and sync the rows into a local table you can analyze offline with query_local_data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_area": {
                        "type": "string",
                        "description": "Subject area name from list_subject_areas",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Field names to sync (see describe_subject_area)",
                    },
                    **{
                        key: value
                        for key, value in _DATE_FILTER_PROPERTIES.items()
                    },
                    "table": {
                        "type": "string",
                        "description": "Optional local table name (default: derived from the subject area)",
                    },
                    "mode": {
                        "type": "string",
                        "description": "replace or append (default replace)",
                        "default": "replace",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows (default 100, max 1000)",
                        "default": 100,
                    },
                },
                "required": ["subject_area", "fields"],
            },
        ),
        Tool(
            name="list_local_tables",
            description="List local tables created by sync_subject_area, with row counts.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="query_local_data",
            description="Run read-only SQL (select) against local tables created by sync_subject_area. Returns a markdown table capped at 100 rows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Read-only SQL query, e.g. select * from <table> limit 20",
                    },
                },
                "required": ["sql"],
            },
        ),
    ]
