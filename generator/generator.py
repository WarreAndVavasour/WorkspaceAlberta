from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, TypedDict

McpType = Literal["node", "python", "http", "http_openapi"]
IntegrationStatus = Literal["native", "openapi", "proxy", "hosted"]


class EnvVar(TypedDict, total=False):
    name: str
    description: str


class McpConfig(TypedDict, total=False):
    server_name: str
    type: McpType
    command: str
    args: list[str]
    url: str
    openapi_url: str
    openapi_url_env: str
    env_vars: list[EnvVar]


class Tool(TypedDict):
    id: str
    display_name: str
    category: str
    description: str
    integration_status: IntegrationStatus
    mcp: McpConfig


@dataclass(frozen=True)
class BuildOptions:
    openapi_wrapper_command: str | None = None
    openapi_wrapper_args: list[str] | None = None


@dataclass(frozen=True)
class GeneratedFiles:
    mcp_json: str
    env_example: str
    integrations_md: str


DEFAULT_CATALOG_PATH = Path(__file__).with_name("catalog.json")
DEFAULT_OPENAPI_WRAPPER_COMMAND = "npx"
DEFAULT_OPENAPI_WRAPPER_ARGS = ["-y", "your-openapi-mcp-wrapper"]


def load_catalog(catalog_path: str | Path = DEFAULT_CATALOG_PATH) -> list[Tool]:
    data = Path(catalog_path).read_text(encoding="utf-8")
    return json.loads(data)


def select_tools(catalog: list[Tool], selected_ids: list[str]) -> list[Tool]:
    by_id = {tool["id"]: tool for tool in catalog}
    missing = [tool_id for tool_id in selected_ids if tool_id not in by_id]

    if missing:
        raise ValueError(f"Unknown tool ids: {', '.join(missing)}")

    return [by_id[tool_id] for tool_id in selected_ids]


def _env_ref(name: str) -> str:
    return f"${{env:{name}}}"


def _env_vars_to_map(env_vars: Iterable[EnvVar]) -> dict[str, str]:
    return {env_var["name"]: _env_ref(env_var["name"]) for env_var in env_vars}


def build_mcp_json(
    selected_tools: list[Tool], options: BuildOptions | None = None
) -> dict[str, object]:
    opts = options or BuildOptions()
    servers: dict[str, object] = {}

    for tool in selected_tools:
        mcp = tool["mcp"]
        env_vars = mcp.get("env_vars", [])
        mcp_type = mcp["type"]

        if mcp_type in ("node", "python"):
            server_config: dict[str, object] = {
                "env": _env_vars_to_map(env_vars),
            }
            if "command" in mcp:
                server_config["command"] = mcp["command"]
            if "args" in mcp:
                server_config["args"] = mcp["args"]
            servers[mcp["server_name"]] = server_config
        elif mcp_type == "http":
            server_config = {
                "type": "http",
                "env": _env_vars_to_map(env_vars),
            }
            if "url" in mcp:
                server_config["url"] = mcp["url"]
            servers[mcp["server_name"]] = server_config
        elif mcp_type == "http_openapi":
            spec = mcp.get("openapi_url")
            if not spec and mcp.get("openapi_url_env"):
                spec = _env_ref(mcp["openapi_url_env"])

            if not spec:
                raise ValueError(
                    "Tool "
                    f"{tool['id']} is http_openapi but missing openapi_url/openapi_url_env"
                )

            servers[mcp["server_name"]] = {
                "command": opts.openapi_wrapper_command
                or DEFAULT_OPENAPI_WRAPPER_COMMAND,
                "args": opts.openapi_wrapper_args or DEFAULT_OPENAPI_WRAPPER_ARGS,
                "env": {
                    "OPENAPI_SPEC_URL": spec,
                    **_env_vars_to_map(env_vars),
                },
            }

    return {"servers": servers}


def build_env_example(selected_tools: list[Tool]) -> str:
    vars_map: dict[str, str | None] = {}
    for tool in selected_tools:
        for env_var in tool["mcp"].get("env_vars", []):
            if env_var["name"] not in vars_map:
                vars_map[env_var["name"]] = env_var.get("description")

    lines: list[str] = []
    for name, description in vars_map.items():
        if description:
            lines.append(f"# {description}")
        lines.append(f"{name}=")
        lines.append("")

    return "\n".join(lines)


def build_integrations_md(selected_tools: list[Tool]) -> str:
    header = [
        "# Integrations",
        "",
        "| SaaS Tool | MCP Server Name | Type | Env Vars |",
        "|-----------|-----------------|------|----------|",
    ]

    rows = []
    for tool in selected_tools:
        mcp = tool["mcp"]
        env_list = "<br>".join(env_var["name"] for env_var in mcp.get("env_vars", []))
        rows.append(
            f"| {tool['display_name']} | `{mcp['server_name']}` | {mcp['type']} | {env_list} |"
        )

    return "\n".join(header + rows)


def _ensure_dir_exists(file_path: Path) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)


def write_workspace_files(
    root: str | Path, selected_tools: list[Tool], options: BuildOptions | None = None
) -> GeneratedFiles:
    root_path = Path(root)
    mcp_json = json.dumps(build_mcp_json(selected_tools, options), indent=2)
    env_example = build_env_example(selected_tools)
    integrations_md = build_integrations_md(selected_tools)

    files = [
        (root_path / ".cursor" / "mcp.json", mcp_json),
        (root_path / "env" / ".env.example", env_example),
        (root_path / "docs" / "INTEGRATIONS.md", integrations_md),
    ]

    for file_path, content in files:
        _ensure_dir_exists(file_path)
        file_path.write_text(content, encoding="utf-8")

    return GeneratedFiles(
        mcp_json=mcp_json, env_example=env_example, integrations_md=integrations_md
    )


def main(args: list[str]) -> int:
    if not args:
        print(
            "Usage: python -m generator.generator <tool_id> [tool_id ...]\n"
            "Example: python -m generator.generator google_drive slack github stripe",
            file=sys.stderr,
        )
        return 1

    catalog = load_catalog()
    selected = select_tools(catalog, args)
    write_workspace_files(Path.cwd(), selected)
    print(
        "Generated .cursor/mcp.json, env/.env.example, docs/INTEGRATIONS.md for tools: "
        + ", ".join(args)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
