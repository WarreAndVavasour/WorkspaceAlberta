from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .generator import Tool, load_catalog, select_tools


@dataclass(frozen=True)
class CodespaceConfig:
    workspace_name: str
    business_problem: str
    owner_name: str
    tools: list[Tool]


def generate_devcontainer(config: CodespaceConfig) -> dict[str, object]:
    secrets: dict[str, str] = {}
    for tool in config.tools:
        for env_var in tool["mcp"].get("env_vars", []):
            if env_var["name"] not in secrets:
                secrets[env_var["name"]] = env_var.get(
                    "description", f"API key for {tool['display_name']}"
                )

    if "ANTHROPIC_API_KEY" not in secrets:
        secrets["ANTHROPIC_API_KEY"] = (
            "Your Anthropic API key for Claude (get from console.anthropic.com)"
        )

    return {
        "name": f"WorkspaceAlberta - {config.workspace_name}",
        "image": "mcr.microsoft.com/devcontainers/python:3.11",
        "features": {
            "ghcr.io/devcontainers/features/node:1": {"version": "20"},
            "ghcr.io/devcontainers/features/github-cli:1": {},
            "ghcr.io/devcontainers/features/common-utils:2": {
                "installZsh": True,
                "configureZshAsDefaultShell": True,
            },
        },
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-python.python",
                    "charliermarsh.ruff",
                ],
                "settings": {
                    "editor.formatOnSave": True,
                    "chat.mcp.discovery.enabled": True,
                    "terminal.integrated.defaultProfile.linux": "zsh",
                    "files.autoSave": "afterDelay",
                    "files.autoSaveDelay": 1000,
                },
            },
            "codespaces": {
                "openFiles": ["docs/WELCOME.md", "problems/business-problem.md"]
            },
        },
        "postCreateCommand": "bash .devcontainer/setup.sh",
        "postStartCommand": "echo 'Workspace ready! Open docs/WELCOME.md to get started.'",
        "secrets": {
            "recommended": [
                {"name": name, "description": description}
                for name, description in secrets.items()
            ]
        },
        "forwardPorts": [3000, 8080, 5000],
        "containerEnv": {
            "WORKSPACE_TYPE": "small-business",
            "WORKSPACE_NAME": config.workspace_name,
        },
        "remoteEnv": {
            "GITHUB_USER": "${localEnv:GITHUB_USER}",
        },
        "hostRequirements": {
            "cpus": 2,
            "memory": "4gb",
            "storage": "32gb",
        },
    }


def generate_mcp_config(config: CodespaceConfig) -> dict[str, object]:
    servers: dict[str, dict[str, object]] = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "${workspaceFolder}"],
            "env": {},
        }
    }

    for tool in config.tools:
        mcp = tool["mcp"]
        if mcp["type"] in ("node", "python"):
            env = {env_var["name"]: f"${{env:{env_var['name']}}}" for env_var in mcp.get("env_vars", [])}
            server_config: dict[str, object] = {"env": env}
            if "command" in mcp:
                server_config["command"] = mcp["command"]
            if "args" in mcp:
                server_config["args"] = mcp["args"]
            servers[mcp["server_name"]] = server_config

    return {
        "$schema": "https://code.visualstudio.com/schemas/mcp.json",
        "servers": servers,
    }


def generate_setup_script(config: CodespaceConfig) -> str:
    secret_checks = {env_var["name"] for tool in config.tools for env_var in tool["mcp"].get("env_vars", [])}
    secret_checks.add("ANTHROPIC_API_KEY")

    checks_code = "\n".join(f'check_secret "{name}"' for name in sorted(secret_checks))

    return f"""#!/bin/bash
# WorkspaceAlberta - Post-Create Setup Script
# Generated for: {config.workspace_name}

set -e

echo "==========================================="
echo "  WorkspaceAlberta Workspace Setup"
echo "  {config.workspace_name}"
echo "==========================================="

# Install project-specific dependencies
if [ -f "requirements.txt" ]; then
    echo "[1/3] Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "[1/3] No requirements.txt found, skipping pip install"
fi

# Install Node dependencies if present (for MCP servers or UI assets)
if [ -f "package.json" ]; then
    echo "[2/3] Installing Node dependencies..."
    npm install
else
    echo "[2/3] No package.json found, skipping npm install"
fi

# Verify MCP configuration exists
echo "[3/3] Verifying MCP configuration..."
if [ -f ".vscode/mcp.json" ]; then
    echo "  - MCP configuration found at .vscode/mcp.json"
    echo "  - Your MCP servers will be available in VS Code"
else
    echo "  - No MCP configuration found"
fi

# Display configured secrets status
echo ""
echo "==========================================="
echo "  Environment Status"
echo "==========================================="

check_secret() {{
    if [ -n "${{!1}}" ]; then
        echo "  [OK] $1 is configured"
    else
        echo "  [--] $1 not set (add in Codespaces secrets)"
    fi
}}

# Check required secrets
{checks_code}

echo ""
echo "==========================================="
echo "  Setup Complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo "  1. Open docs/WELCOME.md for your personalized guide"
echo "  2. Add any missing API keys in Codespaces secrets"
echo "  3. Start working on your business problem!"
echo ""
"""


def generate_welcome_docs(config: CodespaceConfig) -> str:
    tools_table = "\n".join(
        f"| {tool['display_name']} | Needs: "
        f"{', '.join(env['name'] for env in tool['mcp'].get('env_vars', [])) or 'None'} | "
        f"{tool['description']} |"
        for tool in config.tools
    )

    return f"""# Welcome to Your AI-Powered Business Workspace

**Workspace:** {config.workspace_name}
**Created for:** {config.owner_name}

Your workspace is ready! This environment is pre-configured with AI tools connected to your business systems.

---

## Quick Start (5 minutes)

### Step 1: Verify Your API Keys

Your workspace needs API keys to connect to your business tools. Check the terminal output above to see which keys are configured.

**To add missing keys:**
1. Click your profile picture (top-right) > Settings
2. Go to "Codespaces" > "Secrets"
3. Add the required secrets for your tools

### Step 2: Open the AI Assistant

Press `Ctrl+Shift+I` (or `Cmd+Shift+I` on Mac) to open the AI chat panel.

The AI assistant (Claude) can help you:
- Analyze your business data
- Create automations
- Build reports and dashboards
- Connect your tools together

### Step 3: Describe Your Problem

Your business problem:

> {config.business_problem}

Start by asking the AI assistant to help you with this specific issue!

---

## Your Connected Tools

The following MCP servers are configured in this workspace:

| Tool | Requirements | What It Does |
|------|--------------|--------------|
| Filesystem | None | Read and write files in your workspace |
{tools_table}

---

## Common Tasks

### Ask the AI to help you with:

1. **Data Analysis**
   > "Show me my top 10 customers by revenue this month"

2. **Automation Ideas**
   > "What repetitive tasks could I automate based on my tools?"

3. **Report Generation**
   > "Create a weekly summary report template for my business"

4. **Integration Building**
   > "Connect my data between [Tool A] and [Tool B]"

---

## Need Help?

- **Documentation**: See the `docs/` folder for detailed guides
- **Your Problem**: Check `problems/business-problem.md` for details
- **Support**: Contact support@workspacealberta.com

---

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Open AI Chat | `Ctrl+Shift+I` | `Cmd+Shift+I` |
| Command Palette | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| Terminal | `Ctrl+`` | `Cmd+`` |
| File Search | `Ctrl+P` | `Cmd+P` |

---

**Ready to get started?** Open the AI chat and describe what you want to accomplish!
"""


def generate_readme(config: CodespaceConfig, repo_url: str) -> str:
    tools_list = "\n".join(
        f"- **{tool['display_name']}** - {tool['description']}"
        for tool in config.tools
    )

    return f"""# {config.workspace_name}

This workspace is pre-configured with AI tools connected to your business systems. Open it in GitHub Codespaces to start working immediately.

## [Launch in Codespaces]

Click the button below to open this workspace:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/{repo_url}?quickstart=1)

---

## What's Included

- **Pre-configured AI assistant** - Claude is ready to help with your business problems
- **MCP Server connections** - Your business tools are connected and ready
- **Zero setup required** - Everything works out of the box

## Getting Started

1. Click "Open in Codespaces" above
2. Wait for the environment to build (2-3 minutes first time)
3. Open `docs/WELCOME.md` for your personalized guide
4. Start chatting with the AI assistant about your business problem

## Your Business Problem

> {config.business_problem}

## Connected Tools

This workspace is configured to connect with:

{tools_list}

## Adding API Keys

Some tools require API keys. Add them in your Codespaces secrets:

1. Go to github.com/settings/codespaces
2. Click "New secret"
3. Add the required keys (see `docs/WELCOME.md` for details)

## Support

- Documentation: `docs/` folder
- Email: support@workspacealberta.com

---

Built with [WorkspaceAlberta](https://github.com/HarleyCoops/WorkspaceAlberta) - AI-powered workspaces for small businesses.
"""


def generate_problem_doc(config: CodespaceConfig) -> str:
    tool_lines = "\n".join(
        f"- **{tool['display_name']}**: {tool['description']}"
        for tool in config.tools
    )

    return f"""# Business Problem

**Owner:** {config.owner_name}
**Workspace:** {config.workspace_name}

---

## The Problem

{config.business_problem}

---

## Connected Tools

The following tools are available to help solve this problem:

{tool_lines}

---

## How to Get Started

1. Open the AI chat panel (`Ctrl+Shift+I`)
2. Describe your problem to the AI assistant
3. Ask specific questions about your data and workflows
4. Let the AI help you build a solution

---

## Notes

*Use this space to track progress, ideas, and solutions as you work.*
"""


def write_codespace_files(
    output_dir: str | Path,
    config: CodespaceConfig,
    repo_url: str = "YOUR-ORG/YOUR-REPO",
) -> None:
    output_path = Path(output_dir)
    devcontainer = generate_devcontainer(config)
    mcp_config = generate_mcp_config(config)
    setup_script = generate_setup_script(config)
    welcome_docs = generate_welcome_docs(config)
    readme = generate_readme(config, repo_url)
    problem_doc = generate_problem_doc(config)

    files: list[tuple[Path, str]] = [
        (output_path / ".devcontainer" / "devcontainer.json", json.dumps(devcontainer, indent=2)),
        (output_path / ".devcontainer" / "setup.sh", setup_script),
        (output_path / ".vscode" / "mcp.json", json.dumps(mcp_config, indent=2)),
        (output_path / "docs" / "WELCOME.md", welcome_docs),
        (output_path / "problems" / "business-problem.md", problem_doc),
        (output_path / "README.md", readme),
    ]

    for file_path, content in files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    print(f"Generated Codespace configuration in {output_path}")
    print("Files created:")
    for file_path, _ in files:
        print(f"  - {file_path.relative_to(output_path)}")


def main(args: list[str]) -> int:
    if len(args) < 4:
        print(
            """
Usage: python -m generator.codespace_generator <output_dir> <workspace_name> <owner_name> <tool_ids...>

Arguments:
  output_dir     Directory to write the Codespace configuration
  workspace_name Name for the workspace
  owner_name     Name of the business owner
  tool_ids       Space-separated list of tool IDs from the catalog

Example:
  python -m generator.codespace_generator ./my-workspace "My Business" "John Doe" stripe google_calendar github

Environment:
  BUSINESS_PROBLEM  Description of the business problem (or edit problems/business-problem.md after generation)
""",
            file=sys.stderr,
        )
        return 1

    output_dir, workspace_name, owner_name, *tool_ids = args
    business_problem = os.environ.get(
        "BUSINESS_PROBLEM",
        "I want to use AI to help me solve my business problems and automate repetitive tasks.",
    )

    try:
        catalog = load_catalog()
        tools = select_tools(catalog, tool_ids)
        config = CodespaceConfig(
            workspace_name=workspace_name,
            business_problem=business_problem,
            owner_name=owner_name,
            tools=tools,
        )
        write_codespace_files(output_dir, config)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
