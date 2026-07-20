#!/usr/bin/env python3
"""
OPERA Core Service — read-only analytics tools behind the OPERA MCP adapters.

This module is the single source of truth for the OPERA Cloud data-tap tool
surface. It has no MCP dependency of its own: stdio/HTTP adapters are thin
wrappers that dispatch into :func:`call_tool_text` here, so every tool
behaves identically however it is reached. Tool declarations (names,
descriptions, input schemas) live in ``opera_core.mcp_tools``.

The module never talks to OPERA directly. It composes the pinned core
interfaces owned elsewhere in ``opera_core``:

- ``config.Settings.from_env()``   — connection + credential settings
- ``auth.TokenManager``            — OAuth token lifecycle
- ``client.GraphQLClient`` / ``client.MockGraphQLClient`` — query transport
- ``catalog``                      — subject-area metadata used to build
  safe, validated GraphQL queries
- ``store.DataStore``              — local CSV exports and DuckDB-style
  tables for offline analysis

When ``settings.mock`` is true the service swaps in ``MockGraphQLClient`` so
the full catalog/store pipeline can be exercised offline.

Security rule: credentials (app key, client secret, password, tokens) are
never echoed into tool output. ``opera_auth_status`` reports only whether
values are present and whether a token can be obtained.
"""

import inspect
import json
import re
from typing import Any

# Tool surface. Every name here maps to an async handler of the same name
# below; ``opera_core.mcp_tools.get_mcp_tools()`` declares the same list for
# the MCP adapters.
TOOL_NAMES = [
    "opera_auth_status",
    "list_subject_areas",
    "describe_subject_area",
    "run_graphql_query",
    "query_subject_area",
    "export_to_csv",
    "sync_subject_area",
    "list_local_tables",
    "query_local_data",
]

MAX_RESULT_CHARS = 20000
MAX_TABLE_ROWS = 100
MAX_QUERY_LIMIT = 1000
DEFAULT_QUERY_LIMIT = 100
VALID_SYNC_MODES = ("replace", "append")

_settings_cache = None


# ============== Core wiring ==============


def get_settings():
    """Load settings from the environment, cached per process.

    Tests patch this function to inject a mock-mode settings object backed
    by a temporary data directory.
    """
    global _settings_cache
    if _settings_cache is None:
        from opera_core.config import Settings

        _settings_cache = Settings.from_env()
    return _settings_cache


def get_store(settings=None):
    """Return a DataStore rooted at the configured data directory."""
    from opera_core.store import DataStore

    settings = settings or get_settings()
    return DataStore(settings.data_dir)


def get_client(settings=None):
    """Return the mock or live GraphQL client for the current settings."""
    from opera_core.auth import TokenManager
    from opera_core.client import GraphQLClient, MockGraphQLClient

    settings = settings or get_settings()
    token_manager = TokenManager(settings)
    if settings.mock:
        # MockGraphQLClient shares GraphQLClient's .execute signature; its
        # constructor may or may not accept a token manager.
        if "token_manager" in inspect.signature(MockGraphQLClient).parameters:
            return MockGraphQLClient(settings, token_manager)
        return MockGraphQLClient(settings)
    return GraphQLClient(settings, token_manager)


# ============== Shared helpers ==============


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Clamp user-provided integer tool arguments to a safe range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def entry_name(entry: Any) -> str:
    """Normalize a catalog entry (dict or string) to its field name."""
    if isinstance(entry, dict):
        return str(entry.get("name") or entry.get("field") or "")
    return str(entry)


def entry_detail(entry: Any) -> str:
    """Normalize a catalog entry to a short human-readable description."""
    if isinstance(entry, dict):
        parts = [str(entry.get(key)) for key in ("type", "description") if entry.get(key)]
        return " — ".join(parts)
    return ""


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render a small markdown table."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        cells = [str(cell).replace("|", "\\|") if cell is not None else "" for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cap_text(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    """Cap tool output size with an explicit truncation note."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n… truncated at {limit} characters."


def graphql_name(raw: str) -> str:
    """Sanitize an arbitrary string into a safe GraphQL identifier."""
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", str(raw).strip())
    if not cleaned:
        raise ValueError("Empty GraphQL name.")
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def subject_field_name(subject_area: str) -> str:
    """Derive the GraphQL query field name for a subject area."""
    cleaned = graphql_name(subject_area)
    return cleaned[0].lower() + cleaned[1:]


def subject_area_names() -> list[str]:
    """Return all catalog subject-area names for error messages."""
    from opera_core import catalog

    return [str(area.get("name", "")) for area in catalog.list_subject_areas()]


def describe_or_raise(subject_area: str) -> dict:
    """Fetch catalog metadata, raising a helpful error for unknown areas."""
    from opera_core import catalog

    try:
        return catalog.describe_subject_area(subject_area)
    except KeyError:
        available = ", ".join(name for name in subject_area_names() if name)
        raise ValueError(
            f"Unknown subject area: {subject_area!r}. "
            f"Available subject areas: {available or '(catalog is empty)'}. "
            "Use list_subject_areas to see them grouped by category."
        )


def subject_area_prefix(name: str) -> str:
    """Derive a grouping prefix from a subject-area name.

    Handles separator-based names ("Financial - X") and the OPERA catalog's
    camelCase convention: leading acronyms ("ARAccountsReceivable" -> "AR")
    and leading words ("BookingsBlock" -> "Bookings").
    """
    name = name.strip()
    if not name:
        return "Other"
    parts = re.split(r"[\s_\-–—:/]+", name, maxsplit=1)
    if len(parts) > 1:
        return parts[0]
    match = re.match(r"^([A-Z]{2,}(?=[A-Z][a-z])|[A-Z][a-z0-9]*)", name)
    prefix = match.group(1) if match else name
    # Two-letter camel words such as "EFolio".
    if len(prefix) == 1 and len(name) > 2 and name[1].isupper() and name[2].islower():
        wider = re.match(r"^[A-Z]{2}[a-z]+", name)
        if wider:
            prefix = wider.group(0)
    return prefix or "Other"


def valid_field_names(description: dict) -> list[str]:
    """Extract the selectable field names from catalog metadata."""
    return [
        name
        for name in (entry_name(entry) for entry in description.get("object_types", []))
        if name
    ]


def validate_fields(subject_area: str, description: dict, fields: list[str]) -> list[str]:
    """Reject unknown fields and sanitize the rest for safe interpolation."""
    known = valid_field_names(description)
    cleaned = []
    unknown = []
    for field in fields:
        name = str(field).strip()
        if known and name not in known:
            unknown.append(name)
            continue
        cleaned.append(graphql_name(name))
    if unknown:
        raise ValueError(
            f"Unknown field(s) for {subject_area}: {', '.join(unknown)}. "
            f"Valid fields: {', '.join(known) or '(none declared)'}. "
            "Use describe_subject_area to inspect fields and filters."
        )
    if not cleaned:
        raise ValueError(
            f"No fields requested for {subject_area}. "
            f"Valid fields: {', '.join(known) or '(none declared)'}."
        )
    return cleaned


def build_subject_area_query(
    subject_area: str,
    fields: list[str],
    date_field: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = DEFAULT_QUERY_LIMIT,
) -> tuple[str, dict]:
    """Build a safe, catalog-validated GraphQL query and its variables."""
    description = describe_or_raise(subject_area)
    selected = validate_fields(subject_area, description, fields)
    limit = clamp_int(limit, default=DEFAULT_QUERY_LIMIT, minimum=1, maximum=MAX_QUERY_LIMIT)

    if (start_date or end_date) and not date_field:
        filters = ", ".join(
            name
            for name in (entry_name(f) for f in description.get("filter_inputs", []))
            if name
        )
        raise ValueError(
            "date_field is required when using start_date/end_date. "
            f"Filter inputs for {subject_area}: {filters or '(none declared)'}."
        )

    query_field = subject_field_name(subject_area)
    var_defs = ["$hotelId: String!", "$limit: Int"]
    args = ["hotelId: $hotelId", "limit: $limit"]
    variables: dict[str, Any] = {"hotelId": get_settings().hotel_id, "limit": limit}

    if start_date or end_date:
        safe_date_field = graphql_name(date_field)
        var_defs.extend(["$startDate: String", "$endDate: String"])
        date_input = []
        if start_date:
            date_input.append("start: $startDate")
            variables["startDate"] = start_date
        if end_date:
            date_input.append("end: $endDate")
            variables["endDate"] = end_date
        args.append(f"{safe_date_field}: {{{', '.join(date_input)}}}")

    selection = "\n    ".join(selected)
    query = (
        f"query SubjectAreaQuery({', '.join(var_defs)}) {{\n"
        f"  {query_field}({', '.join(args)}) {{\n"
        f"    {selection}\n"
        f"  }}\n"
        f"}}"
    )
    return query, variables


def extract_rows(payload: dict, subject_area: str) -> list[dict]:
    """Pull row dicts out of a GraphQL response for a subject-area query."""
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return []
    value = data.get(subject_field_name(subject_area))
    if value is None and len(data) == 1:
        value = next(iter(data.values()))
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        for key in ("nodes", "rows", "items", "results"):
            if isinstance(value.get(key), list):
                return [row for row in value[key] if isinstance(row, dict)]
        if isinstance(value.get("edges"), list):
            return [
                edge["node"]
                for edge in value["edges"]
                if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
            ]
        return [value]
    return []


def query_subject_area_rows(args: dict) -> tuple[str, list[dict], str]:
    """Run a validated subject-area query. Returns (subject_area, rows, query)."""
    subject_area = str(args.get("subject_area", "")).strip()
    if not subject_area:
        raise ValueError("subject_area is required. Use list_subject_areas to see options.")
    fields = args.get("fields") or []
    if isinstance(fields, str):
        fields = [part.strip() for part in fields.split(",") if part.strip()]
    if not fields:
        raise ValueError(
            "fields is required (a list of field names). "
            "Use describe_subject_area to see valid fields."
        )
    query, variables = build_subject_area_query(
        subject_area,
        fields,
        date_field=str(args.get("date_field", "") or "").strip(),
        start_date=str(args.get("start_date", "") or "").strip(),
        end_date=str(args.get("end_date", "") or "").strip(),
        limit=args.get("limit", DEFAULT_QUERY_LIMIT),
    )
    payload = get_client().execute(query, variables)
    return subject_area, extract_rows(payload, subject_area), query


def rows_to_markdown(rows: list[dict], cap: int = MAX_TABLE_ROWS) -> str:
    """Render row dicts as a capped markdown table."""
    if not rows:
        return "(no rows)"
    headers: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(str(key))
    shown = rows[:cap]
    table = markdown_table(headers, [[row.get(h) for h in headers] for row in shown])
    if len(rows) > cap:
        table += f"\n\n… showing {cap} of {len(rows)} rows."
    return table


# ============== Tool handlers ==============


async def opera_auth_status(args: dict) -> str:
    """Report configuration and token readiness without echoing secrets."""
    settings = get_settings()
    checks = [
        ("base_url", settings.base_url),
        ("graphql_path", settings.graphql_path),
        ("token_path", settings.token_path),
        ("app_key", settings.app_key),
        ("client_id", settings.client_id),
        ("client_secret", settings.client_secret),
        ("hotel_id", settings.hotel_id),
        ("username", settings.username),
        ("password", settings.password),
        ("grant_type", settings.grant_type),
    ]

    lines = ["# OPERA Auth Status", ""]
    lines.append(f"- **Mode:** {'mock (offline demo data)' if settings.mock else 'live'}")
    lines.append(f"- **Hotel:** {settings.hotel_id or '(not set)'}")
    lines.append(f"- **Data dir:** `{settings.data_dir}`")
    lines.append("")
    lines.append("## Configuration")
    for name, value in checks:
        lines.append(f"- **{name}:** {'set' if value else 'not set'}")
    lines.append("")
    lines.append("Secrets are never displayed; 'set' only means a value is present.")
    lines.append("")

    lines.append("## Token")
    if settings.mock:
        lines.append("- Mock mode: no token required. Queries are answered locally.")
    else:
        try:
            from opera_core.auth import AuthError, TokenManager

            token = TokenManager(settings).token()
            lines.append(f"- Token obtainable: yes ({len(token)} characters, value hidden)")
        except AuthError as exc:
            lines.append(f"- Token obtainable: no — {exc}")
        except Exception as exc:  # network errors, misconfiguration, etc.
            lines.append(f"- Token obtainable: no — {type(exc).__name__}: {exc}")
    return "\n".join(lines)


async def list_subject_areas(args: dict) -> str:
    """List OPERA R&A subject areas grouped by name prefix."""
    from opera_core import catalog

    areas = catalog.list_subject_areas()
    if not areas:
        return "No subject areas are available in the catalog."

    groups: dict[str, list[dict]] = {}
    for area in areas:
        groups.setdefault(subject_area_prefix(str(area.get("name", ""))), []).append(area)

    lines = [f"# OPERA Subject Areas ({len(areas)})", ""]
    for prefix in sorted(groups):
        group = groups[prefix]
        lines.append(f"## {prefix} ({len(group)})")
        lines.append(
            markdown_table(
                ["Name", "Title", "Version", "Description"],
                [
                    [
                        area.get("name", ""),
                        area.get("title", ""),
                        area.get("version", ""),
                        str(area.get("description", ""))[:120],
                    ]
                    for area in group
                ],
            )
        )
        lines.append("")
    lines.append("Use describe_subject_area with a name to see fields, filters, and an example query.")
    return "\n".join(lines)


async def describe_subject_area(args: dict) -> str:
    """Describe one subject area: fields, filters, and an example query."""
    name = str(args.get("name", "")).strip()
    if not name:
        return "Error: name is required. Use list_subject_areas to see available subject areas."

    description = describe_or_raise(name)

    lines = [f"# {description.get('title') or name}", ""]
    lines.append(f"- **Name:** `{description.get('name', name)}`")
    if description.get("version"):
        lines.append(f"- **Version:** {description['version']}")
    if description.get("description"):
        lines.append(f"- **Description:** {description['description']}")
    lines.append("")

    object_types = description.get("object_types", [])
    lines.append(f"## Fields ({len(object_types)})")
    if object_types:
        lines.append(
            markdown_table(
                ["Field", "Details"],
                [[entry_name(entry), entry_detail(entry)] for entry in object_types],
            )
        )
    else:
        lines.append("(none declared)")
    lines.append("")

    filter_inputs = description.get("filter_inputs", [])
    lines.append(f"## Filters ({len(filter_inputs)})")
    if filter_inputs:
        lines.append(
            markdown_table(
                ["Filter", "Details"],
                [[entry_name(entry), entry_detail(entry)] for entry in filter_inputs],
            )
        )
    else:
        lines.append("(none declared)")
    lines.append("")

    example = description.get("example_query", "")
    if example:
        lines.append("## Example Query")
        lines.append("```graphql")
        lines.append(str(example).strip())
        lines.append("```")
    return "\n".join(lines)


async def run_graphql_query(args: dict) -> str:
    """Pass a raw GraphQL query through to OPERA (read-only analytics)."""
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query is required."

    variables = args.get("variables")
    if isinstance(variables, str):
        try:
            variables = json.loads(variables)
        except json.JSONDecodeError as exc:
            return f"Error: variables is not valid JSON: {exc}"
    if variables is not None and not isinstance(variables, dict):
        return "Error: variables must be a JSON object."

    payload = get_client().execute(query, variables)
    body = json.dumps(payload, indent=2, default=str)
    return "# GraphQL Result\n\n```json\n" + cap_text(body) + "\n```"


async def query_subject_area(args: dict) -> str:
    """Run a safe, catalog-validated query against a subject area."""
    subject_area, rows, query = await _run_subject_area(args)
    lines = [f"# {subject_area}", ""]
    lines.append(f"Returned {len(rows)} row(s).")
    lines.append("")
    lines.append(rows_to_markdown(rows))
    lines.append("")
    lines.append("<details><summary>Generated query</summary>\n")
    lines.append("```graphql")
    lines.append(query)
    lines.append("```\n</details>")
    return cap_text("\n".join(lines))


async def _run_subject_area(args: dict) -> tuple[str, list[dict], str]:
    return query_subject_area_rows(args)


async def export_to_csv(args: dict) -> str:
    """Query a subject area and export the rows to a CSV file."""
    subject_area, rows, _query = await _run_subject_area(args)
    if not rows:
        return f"Query against {subject_area} returned no rows; nothing exported."

    name = str(args.get("name", "") or "").strip() or f"{subject_field_name(subject_area)}_export"
    store = get_store()
    path = store.save_csv(name, rows)

    lines = [f"# CSV Export: {subject_area}", ""]
    lines.append(f"- **Rows:** {len(rows)}")
    lines.append(f"- **File:** `{path}`")
    return "\n".join(lines)


async def sync_subject_area(args: dict) -> str:
    """Query a subject area and sync the rows into a local table."""
    subject_area, rows, _query = await _run_subject_area(args)

    table = str(args.get("table", "") or "").strip() or re.sub(
        r"[^0-9a-z_]", "_", subject_field_name(subject_area).lower()
    )
    mode = str(args.get("mode", "replace") or "replace").strip().lower()
    if mode not in VALID_SYNC_MODES:
        return f"Error: mode must be one of {', '.join(VALID_SYNC_MODES)}."

    store = get_store()
    rowcount = store.save_table(table, rows, mode)

    lines = [f"# Sync: {subject_area}", ""]
    lines.append(f"- **Table:** `{table}`")
    lines.append(f"- **Mode:** {mode}")
    lines.append(f"- **Rows written:** {rowcount}")
    lines.append("")
    lines.append(f"Query it with query_local_data, e.g. `select * from {table} limit 20`.")
    return "\n".join(lines)


async def list_local_tables(args: dict) -> str:
    """List local tables created by sync_subject_area."""
    store = get_store()
    tables = store.list_tables()
    if not tables:
        return "No local tables yet. Use sync_subject_area to pull data into a table."

    lines = [f"# Local Tables ({len(tables)})", ""]
    rows = []
    for table in tables:
        if isinstance(table, dict):
            rows.append(
                [
                    table.get("name") or table.get("table") or "",
                    table.get("rows", table.get("row_count", "")),
                    table.get("updated_at") or table.get("updated") or "",
                ]
            )
        else:
            rows.append([str(table), "", ""])
    lines.append(markdown_table(["Table", "Rows", "Updated"], rows))
    lines.append("")
    lines.append("Query one with query_local_data, e.g. `select * from <table> limit 20`.")
    return "\n".join(lines)


async def query_local_data(args: dict) -> str:
    """Run read-only SQL against local synced tables."""
    sql = str(args.get("sql", "")).strip()
    if not sql:
        return "Error: sql is required. Example: select * from <table> limit 20"
    if not re.match(r"^\s*(select|with|show|describe|explain)\b", sql, flags=re.IGNORECASE):
        return "Error: only read-only queries (select/with/show/describe/explain) are allowed."

    store = get_store()
    result = store.run_sql(sql)

    lines = ["# Query Result", ""]
    if isinstance(result, dict):
        columns = result.get("columns") or []
        rows = result.get("rows") or []
        if rows and isinstance(rows[0], dict):
            lines.append(rows_to_markdown(rows, cap=MAX_TABLE_ROWS))
            total = len(rows)
        else:
            shown = rows[:MAX_TABLE_ROWS]
            if not columns and shown:
                columns = [str(i) for i in range(len(shown[0]))]
            lines.append(markdown_table([str(c) for c in columns], [list(r) for r in shown]))
            total = len(rows)
        lines.append("")
        lines.append(f"{min(total, MAX_TABLE_ROWS)} of {total} row(s) shown.")
    else:
        lines.append("```json")
        lines.append(cap_text(json.dumps(result, indent=2, default=str)))
        lines.append("```")
    return cap_text("\n".join(lines))


# ============== Dispatch ==============


async def call_tool_text(name: str, arguments: dict[str, Any] | None = None) -> str:
    """Run an OPERA tool and return markdown text without any MCP dependency."""
    args = arguments or {}
    handler = globals().get(name)
    if name not in TOOL_NAMES or handler is None:
        return (
            f"Unknown tool: {name}\n\n"
            f"Available tools: {', '.join(TOOL_NAMES)}\n\n"
            "Start with opera_auth_status to check the connection, then "
            "list_subject_areas to browse available analytics data."
        )

    try:
        return await handler(args)
    except Exception as exc:
        return f"Error: {exc}"
