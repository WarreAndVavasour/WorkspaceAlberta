import fs from "fs";
import path from "path";
import { loadCatalog, selectTools, Tool } from "./generator";

/**
 * Codespace Generator
 * 
 * Generates complete GitHub Codespace configurations including:
 * - .devcontainer/devcontainer.json
 * - .vscode/mcp.json
 * - Setup scripts
 * - Welcome documentation
 */

interface CodespaceConfig {
  workspaceName: string;
  businessProblem: string;
  ownerName: string;
  tools: Tool[];
}

interface DevContainerJson {
  name: string;
  image: string;
  features: Record<string, unknown>;
  customizations: {
    vscode: {
      extensions: string[];
      settings: Record<string, unknown>;
    };
    codespaces: {
      openFiles: string[];
    };
  };
  postCreateCommand: string;
  postStartCommand: string;
  secrets: {
    recommended: Array<{
      name: string;
      description: string;
    }>;
  };
  forwardPorts: number[];
  containerEnv: Record<string, string>;
  remoteEnv: Record<string, string>;
  hostRequirements: {
    cpus: number;
    memory: string;
    storage: string;
  };
}

interface McpServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
}

interface VscodeMcpJson {
  $schema: string;
  servers: Record<string, McpServerConfig>;
}

/**
 * Generate the devcontainer.json file
 */
function generateDevContainer(config: CodespaceConfig): DevContainerJson {
  // Collect all unique secrets from selected tools
  const secrets = new Map<string, string>();
  for (const tool of config.tools) {
    for (const envVar of tool.mcp.env_vars) {
      if (!secrets.has(envVar.name)) {
        secrets.set(envVar.name, envVar.description || `API key for ${tool.display_name}`);
      }
    }
  }

  // Add Anthropic API key as always recommended
  if (!secrets.has("ANTHROPIC_API_KEY")) {
    secrets.set("ANTHROPIC_API_KEY", "Your Anthropic API key for Claude (get from console.anthropic.com)");
  }

  return {
    name: `WorkspaceAlberta - ${config.workspaceName}`,
    image: "mcr.microsoft.com/devcontainers/javascript-node:20",
    features: {
      "ghcr.io/devcontainers/features/python:1": {
        version: "3.11",
      },
      "ghcr.io/devcontainers/features/github-cli:1": {},
      "ghcr.io/devcontainers/features/common-utils:2": {
        installZsh: true,
        configureZshAsDefaultShell: true,
      },
    },
    customizations: {
      vscode: {
        extensions: [
          "ms-python.python",
          "dbaeumer.vscode-eslint",
          "esbenp.prettier-vscode",
          "bradlc.vscode-tailwindcss",
          "ms-vscode.vscode-typescript-next",
        ],
        settings: {
          "editor.formatOnSave": true,
          "editor.defaultFormatter": "esbenp.prettier-vscode",
          "chat.mcp.discovery.enabled": true,
          "terminal.integrated.defaultProfile.linux": "zsh",
          "files.autoSave": "afterDelay",
          "files.autoSaveDelay": 1000,
        },
      },
      codespaces: {
        openFiles: ["docs/WELCOME.md", "problems/business-problem.md"],
      },
    },
    postCreateCommand: "bash .devcontainer/setup.sh",
    postStartCommand: "echo 'Workspace ready! Open docs/WELCOME.md to get started.'",
    secrets: {
      recommended: Array.from(secrets.entries()).map(([name, description]) => ({
        name,
        description,
      })),
    },
    forwardPorts: [3000, 8080, 5000],
    containerEnv: {
      WORKSPACE_TYPE: "small-business",
      WORKSPACE_NAME: config.workspaceName,
      NODE_ENV: "development",
    },
    remoteEnv: {
      GITHUB_USER: "${localEnv:GITHUB_USER}",
    },
    hostRequirements: {
      cpus: 2,
      memory: "4gb",
      storage: "32gb",
    },
  };
}

/**
 * Generate the .vscode/mcp.json file
 */
function generateMcpConfig(config: CodespaceConfig): VscodeMcpJson {
  const servers: Record<string, McpServerConfig> = {
    // Always include filesystem server
    filesystem: {
      command: "npx",
      args: ["-y", "@modelcontextprotocol/server-filesystem", "${workspaceFolder}"],
      env: {},
    },
  };

  // Add servers for each selected tool
  for (const tool of config.tools) {
    const mcp = tool.mcp;

    if (mcp.type === "node" || mcp.type === "python") {
      const env: Record<string, string> = {};
      for (const envVar of mcp.env_vars) {
        env[envVar.name] = `\${env:${envVar.name}}`;
      }

      servers[mcp.server_name] = {
        command: mcp.command || "npx",
        args: mcp.args || [],
        env,
      };
    }
  }

  return {
    $schema: "https://code.visualstudio.com/schemas/mcp.json",
    servers,
  };
}

/**
 * Generate the setup.sh script
 */
function generateSetupScript(config: CodespaceConfig): string {
  const secretChecks = new Set<string>();
  for (const tool of config.tools) {
    for (const envVar of tool.mcp.env_vars) {
      secretChecks.add(envVar.name);
    }
  }
  secretChecks.add("ANTHROPIC_API_KEY");

  const checksCode = Array.from(secretChecks)
    .map((name) => `check_secret "${name}"`)
    .join("\n");

  return `#!/bin/bash
# WorkspaceAlberta - Post-Create Setup Script
# Generated for: ${config.workspaceName}

set -e

echo "==========================================="
echo "  WorkspaceAlberta Workspace Setup"
echo "  ${config.workspaceName}"
echo "==========================================="

# Install Node.js MCP dependencies globally
echo "[1/4] Installing MCP server dependencies..."
npm install -g @modelcontextprotocol/sdk 2>/dev/null || true

# Install any project-specific dependencies
if [ -f "package.json" ]; then
    echo "[2/4] Installing project dependencies..."
    npm install
else
    echo "[2/4] No package.json found, skipping npm install"
fi

# Install Python dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "[3/4] Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "[3/4] No requirements.txt found, skipping pip install"
fi

# Verify MCP configuration exists
echo "[4/4] Verifying MCP configuration..."
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

check_secret() {
    if [ -n "\${!1}" ]; then
        echo "  [OK] $1 is configured"
    else
        echo "  [--] $1 not set (add in Codespaces secrets)"
    fi
}

# Check required secrets
${checksCode}

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
`;
}

/**
 * Generate the WELCOME.md documentation
 */
function generateWelcomeDocs(config: CodespaceConfig): string {
  const toolsTable = config.tools
    .map((tool) => {
      const requiredSecrets = tool.mcp.env_vars.map((v) => v.name).join(", ") || "None";
      return `| ${tool.display_name} | Needs: ${requiredSecrets} | ${tool.description} |`;
    })
    .join("\n");

  return `# Welcome to Your AI-Powered Business Workspace

**Workspace:** ${config.workspaceName}
**Created for:** ${config.ownerName}

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

Press \`Ctrl+Shift+I\` (or \`Cmd+Shift+I\` on Mac) to open the AI chat panel.

The AI assistant (Claude) can help you:
- Analyze your business data
- Create automations
- Build reports and dashboards
- Connect your tools together

### Step 3: Describe Your Problem

Your business problem:

> ${config.businessProblem}

Start by asking the AI assistant to help you with this specific issue!

---

## Your Connected Tools

The following MCP servers are configured in this workspace:

| Tool | Requirements | What It Does |
|------|--------------|--------------|
| Filesystem | None | Read and write files in your workspace |
${toolsTable}

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

- **Documentation**: See the \`docs/\` folder for detailed guides
- **Your Problem**: Check \`problems/business-problem.md\` for details
- **Support**: Contact support@workspacealberta.com

---

## Keyboard Shortcuts

| Action | Windows/Linux | Mac |
|--------|---------------|-----|
| Open AI Chat | \`Ctrl+Shift+I\` | \`Cmd+Shift+I\` |
| Command Palette | \`Ctrl+Shift+P\` | \`Cmd+Shift+P\` |
| Terminal | \`Ctrl+\`\` | \`Cmd+\`\` |
| File Search | \`Ctrl+P\` | \`Cmd+P\` |

---

**Ready to get started?** Open the AI chat and describe what you want to accomplish!
`;
}

/**
 * Generate the README.md file
 */
function generateReadme(config: CodespaceConfig, repoUrl: string): string {
  const toolsList = config.tools
    .map((tool) => `- **${tool.display_name}** - ${tool.description}`)
    .join("\n");

  return `# ${config.workspaceName}

This workspace is pre-configured with AI tools connected to your business systems. Open it in GitHub Codespaces to start working immediately.

## [Launch in Codespaces]

Click the button below to open this workspace:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/${repoUrl}?quickstart=1)

---

## What's Included

- **Pre-configured AI assistant** - Claude is ready to help with your business problems
- **MCP Server connections** - Your business tools are connected and ready
- **Zero setup required** - Everything works out of the box

## Getting Started

1. Click "Open in Codespaces" above
2. Wait for the environment to build (2-3 minutes first time)
3. Open \`docs/WELCOME.md\` for your personalized guide
4. Start chatting with the AI assistant about your business problem

## Your Business Problem

> ${config.businessProblem}

## Connected Tools

This workspace is configured to connect with:

${toolsList}

## Adding API Keys

Some tools require API keys. Add them in your Codespaces secrets:

1. Go to github.com/settings/codespaces
2. Click "New secret"
3. Add the required keys (see \`docs/WELCOME.md\` for details)

## Support

- Documentation: \`docs/\` folder
- Email: support@workspacealberta.com

---

Built with [WorkspaceAlberta](https://github.com/HarleyCoops/WorkspaceAlberta) - AI-powered workspaces for small businesses.
`;
}

/**
 * Generate the business problem markdown file
 */
function generateProblemDoc(config: CodespaceConfig): string {
  return `# Business Problem

**Owner:** ${config.ownerName}
**Workspace:** ${config.workspaceName}

---

## The Problem

${config.businessProblem}

---

## Connected Tools

The following tools are available to help solve this problem:

${config.tools.map((t) => `- **${t.display_name}**: ${t.description}`).join("\n")}

---

## How to Get Started

1. Open the AI chat panel (\`Ctrl+Shift+I\`)
2. Describe your problem to the AI assistant
3. Ask specific questions about your data and workflows
4. Let the AI help you build a solution

---

## Notes

*Use this space to track progress, ideas, and solutions as you work.*
`;
}

/**
 * Write all Codespace files to the output directory
 */
export function writeCodespaceFiles(
  outputDir: string,
  config: CodespaceConfig,
  repoUrl: string = "YOUR-ORG/YOUR-REPO"
): void {
  const devcontainer = generateDevContainer(config);
  const mcpConfig = generateMcpConfig(config);
  const setupScript = generateSetupScript(config);
  const welcomeDocs = generateWelcomeDocs(config);
  const readme = generateReadme(config, repoUrl);
  const problemDoc = generateProblemDoc(config);

  const files: [string, string][] = [
    [path.join(outputDir, ".devcontainer", "devcontainer.json"), JSON.stringify(devcontainer, null, 2)],
    [path.join(outputDir, ".devcontainer", "setup.sh"), setupScript],
    [path.join(outputDir, ".vscode", "mcp.json"), JSON.stringify(mcpConfig, null, 2)],
    [path.join(outputDir, "docs", "WELCOME.md"), welcomeDocs],
    [path.join(outputDir, "problems", "business-problem.md"), problemDoc],
    [path.join(outputDir, "README.md"), readme],
  ];

  for (const [filePath, content] of files) {
    const dir = path.dirname(filePath);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(filePath, content, "utf8");
  }

  console.log(`Generated Codespace configuration in ${outputDir}`);
  console.log("Files created:");
  for (const [filePath] of files) {
    console.log(`  - ${path.relative(outputDir, filePath)}`);
  }
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 4) {
    console.error(`
Usage: ts-node codespace-generator.ts <output_dir> <workspace_name> <owner_name> <tool_ids...>

Arguments:
  output_dir     Directory to write the Codespace configuration
  workspace_name Name for the workspace
  owner_name     Name of the business owner
  tool_ids       Space-separated list of tool IDs from the catalog

Example:
  ts-node codespace-generator.ts ./my-workspace "My Business" "John Doe" stripe google_calendar github

Environment:
  BUSINESS_PROBLEM  Description of the business problem (or edit problems/business-problem.md after generation)
`);
    process.exit(1);
  }

  const [outputDir, workspaceName, ownerName, ...toolIds] = args;
  const businessProblem =
    process.env.BUSINESS_PROBLEM ||
    "I want to use AI to help me solve my business problems and automate repetitive tasks.";

  try {
    const catalog = loadCatalog();
    const tools = selectTools(catalog, toolIds);

    const config: CodespaceConfig = {
      workspaceName,
      businessProblem,
      ownerName,
      tools,
    };

    writeCodespaceFiles(outputDir, config);
  } catch (error) {
    console.error("Error:", (error as Error).message);
    process.exit(1);
  }
}

export { CodespaceConfig, generateDevContainer, generateMcpConfig };
