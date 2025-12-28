#!/usr/bin/env python3
"""
WorkspaceAlberta Generator

Generates Cursor IDE workspace configurations from a tool catalog.
Outputs: .cursor/mcp.json, env/.env.example, docs/INTEGRATIONS.md
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Type definitions
McpType = str  # "node" | "python" | "http" | "http_openapi"
IntegrationStatus = str  # "native" | "openapi" | "proxy" | "hosted"

DEFAULT_CATALOG_PATH = Path(__file__).parent / "catalog.json"
DEFAULT_OPENAPI_WRAPPER_COMMAND = "npx"
DEFAULT_OPENAPI_WRAPPER_ARGS = ["-y", "your-openapi-mcp-wrapper"]


def load_catalog(catalog_path: Optional[Path] = None) -> list[dict]:
    """Load the tool catalog from JSON file."""
    path = catalog_path or DEFAULT_CATALOG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_tools(catalog: list[dict], selected_ids: list[str]) -> list[dict]:
    """Select tools from catalog by ID, validating all exist."""
    by_id = {tool["id"]: tool for tool in catalog}
    missing = [id for id in selected_ids if id not in by_id]

    if missing:
        raise ValueError(f"Unknown tool ids: {', '.join(missing)}")

    return [by_id[id] for id in selected_ids]


def env_vars_to_map(env_vars: list[dict]) -> dict[str, str]:
    """Convert env_vars list to environment variable map."""
    return {v["name"]: f"${{env:{v['name']}}}" for v in env_vars}


def build_mcp_json(
    selected_tools: list[dict],
    openapi_wrapper_command: Optional[str] = None,
    openapi_wrapper_args: Optional[list[str]] = None
) -> dict:
    """Build the .cursor/mcp.json configuration."""
    servers = {}

    wrapper_cmd = openapi_wrapper_command or DEFAULT_OPENAPI_WRAPPER_COMMAND
    wrapper_args = openapi_wrapper_args or DEFAULT_OPENAPI_WRAPPER_ARGS

    for tool in selected_tools:
        m = tool["mcp"]
        mcp_type = m["type"]

        if mcp_type in ("node", "python"):
            servers[m["server_name"]] = {
                "command": m.get("command"),
                "args": m.get("args", []),
                "env": env_vars_to_map(m.get("env_vars", []))
            }
        elif mcp_type == "http":
            servers[m["server_name"]] = {
                "type": "http",
                "url": m.get("url"),
                "env": env_vars_to_map(m.get("env_vars", []))
            }
        elif mcp_type == "http_openapi":
            openapi_url = m.get("openapi_url")
            openapi_url_env = m.get("openapi_url_env")

            if openapi_url:
                spec = openapi_url
            elif openapi_url_env:
                spec = f"${{env:{openapi_url_env}}}"
            else:
                raise ValueError(
                    f"Tool {tool['id']} is http_openapi but missing openapi_url/openapi_url_env"
                )

            servers[m["server_name"]] = {
                "command": wrapper_cmd,
                "args": wrapper_args,
                "env": {
                    "OPENAPI_SPEC_URL": spec,
                    **env_vars_to_map(m.get("env_vars", []))
                }
            }

    return {"servers": servers}


def build_env_example(selected_tools: list[dict]) -> str:
    """Build the .env.example file content."""
    vars_map: dict[str, Optional[str]] = {}

    for tool in selected_tools:
        for v in tool["mcp"].get("env_vars", []):
            if v["name"] not in vars_map:
                vars_map[v["name"]] = v.get("description")

    lines = []
    for name, description in vars_map.items():
        if description:
            lines.append(f"# {description}")
        lines.append(f"{name}=")
        lines.append("")

    return "\n".join(lines)


def build_integrations_md(selected_tools: list[dict]) -> str:
    """Build the INTEGRATIONS.md documentation."""
    header = [
        "# Integrations",
        "",
        "| SaaS Tool | MCP Server Name | Type | Env Vars |",
        "|-----------|-----------------|------|----------|",
    ]

    rows = []
    for t in selected_tools:
        m = t["mcp"]
        env_list = "<br>".join(v["name"] for v in m.get("env_vars", []))
        rows.append(f"| {t['display_name']} | `{m['server_name']}` | {m['type']} | {env_list} |")

    return "\n".join(header + rows)


def ensure_dir_exists(file_path: Path) -> None:
    """Ensure the parent directory exists."""
    file_path.parent.mkdir(parents=True, exist_ok=True)


def write_workspace_files(
    root: Path,
    selected_tools: list[dict],
    openapi_wrapper_command: Optional[str] = None,
    openapi_wrapper_args: Optional[list[str]] = None
) -> dict[str, str]:
    """Write all workspace configuration files."""
    mcp_json = json.dumps(
        build_mcp_json(selected_tools, openapi_wrapper_command, openapi_wrapper_args),
        indent=2
    )
    env_example = build_env_example(selected_tools)
    integrations_md = build_integrations_md(selected_tools)

    files = [
        (root / ".cursor" / "mcp.json", mcp_json),
        (root / "env" / ".env.example", env_example),
        (root / "docs" / "INTEGRATIONS.md", integrations_md),
    ]

    for file_path, content in files:
        ensure_dir_exists(file_path)
        file_path.write_text(content, encoding="utf-8")

    return {
        "mcp_json": mcp_json,
        "env_example": env_example,
        "integrations_md": integrations_md
    }


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: python generator.py <tool_id> [tool_id ...]\n"
            "Example: python generator.py google_drive slack github stripe",
            file=sys.stderr
        )
        sys.exit(1)

    tool_ids = sys.argv[1:]

    catalog = load_catalog()
    selected = select_tools(catalog, tool_ids)
    write_workspace_files(Path.cwd(), selected)

    print(
        f"Generated .cursor/mcp.json, env/.env.example, docs/INTEGRATIONS.md "
        f"for tools: {', '.join(tool_ids)}"
    )


if __name__ == "__main__":
    main()
