/**
 * WorkspaceAlberta Generator (TypeScript)
 *
 * Generates Cursor IDE workspace configurations from a tool catalog.
 * Outputs: .cursor/mcp.json, env/.env.example, docs/INTEGRATIONS.md
 *
 * Usage:
 *   npx ts-node generator/generator.ts [options] <tool_id> [tool_id ...]
 *
 * Options:
 *   --list          List all available tools
 *   --dry-run       Preview without writing files
 *   --out <path>    Output directory (default: current directory)
 *   --with-readme   Also generate README.md
 *   --help          Show help
 */

import fs from "fs";
import path from "path";
import minimist from "minimist";

// Types
type McpType = "node" | "python" | "http" | "http_openapi";
type IntegrationStatus = "native" | "openapi" | "proxy" | "hosted";

interface EnvVar {
  name: string;
  description?: string;
}

interface McpConfig {
  server_name: string;
  type: McpType;
  command?: string;
  args?: string[];
  url?: string;
  openapi_url?: string;
  openapi_url_env?: string;
  env_vars: EnvVar[];
}

export interface Tool {
  id: string;
  display_name: string;
  category: string;
  description: string;
  integration_status: IntegrationStatus;
  mcp: McpConfig;
}

export interface BuildOptions {
  openapiWrapperCommand?: string;
  openapiWrapperArgs?: string[];
}

// Constants
const DEFAULT_CATALOG_PATH = path.join(__dirname, "catalog.json");
const DEFAULT_OPENAPI_WRAPPER_COMMAND = "npx";
const DEFAULT_OPENAPI_WRAPPER_ARGS = ["-y", "your-openapi-mcp-wrapper"];

/**
 * Load the tool catalog from JSON file
 */
export function loadCatalog(catalogPath: string = DEFAULT_CATALOG_PATH): Tool[] {
  const data = fs.readFileSync(catalogPath, "utf8");
  return JSON.parse(data);
}

/**
 * Select tools from catalog by ID, validating all exist
 */
export function selectTools(catalog: Tool[], selectedIds: string[]): Tool[] {
  const byId = new Map(catalog.map((tool) => [tool.id, tool]));
  const missing = selectedIds.filter((id) => !byId.has(id));

  if (missing.length) {
    throw new Error(`Unknown tool ids: ${missing.join(", ")}`);
  }

  return selectedIds.map((id) => byId.get(id)!);
}

/**
 * Convert env_vars list to environment variable map
 */
function envVarsToMap(envVars: EnvVar[]): Record<string, string> {
  return Object.fromEntries(envVars.map((v) => [v.name, `\${env:${v.name}}`]));
}

/**
 * Build the .cursor/mcp.json configuration
 */
export function buildMcpJson(
  selectedTools: Tool[],
  options: BuildOptions = {}
): Record<string, unknown> {
  const servers: Record<string, unknown> = {};

  const wrapperCmd = options.openapiWrapperCommand ?? DEFAULT_OPENAPI_WRAPPER_COMMAND;
  const wrapperArgs = options.openapiWrapperArgs ?? DEFAULT_OPENAPI_WRAPPER_ARGS;

  for (const tool of selectedTools) {
    const m = tool.mcp;

    if (m.type === "node" || m.type === "python") {
      servers[m.server_name] = {
        command: m.command,
        args: m.args ?? [],
        env: envVarsToMap(m.env_vars),
      };
    } else if (m.type === "http") {
      servers[m.server_name] = {
        type: "http",
        url: m.url,
        env: envVarsToMap(m.env_vars),
      };
    } else if (m.type === "http_openapi") {
      const spec =
        m.openapi_url ?? (m.openapi_url_env ? `\${env:${m.openapi_url_env}}` : undefined);

      if (!spec) {
        throw new Error(
          `Tool ${tool.id} is http_openapi but missing openapi_url/openapi_url_env`
        );
      }

      servers[m.server_name] = {
        command: wrapperCmd,
        args: wrapperArgs,
        env: {
          OPENAPI_SPEC_URL: spec,
          ...envVarsToMap(m.env_vars),
        },
      };
    }
  }

  return { servers };
}

/**
 * Build the .env.example file content
 */
export function buildEnvExample(selectedTools: Tool[]): string {
  const vars = new Map<string, string | undefined>();

  for (const tool of selectedTools) {
    for (const v of tool.mcp.env_vars) {
      if (!vars.has(v.name)) {
        vars.set(v.name, v.description);
      }
    }
  }

  const lines: string[] = [];
  for (const [name, description] of vars.entries()) {
    if (description) lines.push(`# ${description}`);
    lines.push(`${name}=`);
    lines.push("");
  }

  return lines.join("\n");
}

/**
 * Build the INTEGRATIONS.md documentation
 */
export function buildIntegrationsMd(selectedTools: Tool[]): string {
  const header = [
    "# Integrations",
    "",
    "| SaaS Tool | MCP Server Name | Type | Env Vars |",
    "|-----------|-----------------|------|----------|",
  ];

  const rows = selectedTools.map((t) => {
    const m = t.mcp;
    const envList = m.env_vars.map((v) => v.name).join("<br>");
    return `| ${t.display_name} | \`${m.server_name}\` | ${m.type} | ${envList} |`;
  });

  return header.concat(rows).join("\n");
}

/**
 * Build a README.md stub
 */
export function buildReadmeMd(selectedTools: Tool[]): string {
  const header = [
    "# Workspace Configuration",
    "",
    "This workspace has been configured with the following integrations:",
    "",
  ];

  const toolList = selectedTools.map(
    (t) => `- **${t.display_name}**: ${t.description}`
  );

  const footer = [
    "",
    "## Setup Instructions",
    "",
    "1. Copy `env/.env.example` to `env/.env`",
    "2. Fill in your API keys and credentials in `env/.env`",
    "3. Open this workspace in Cursor",
    "4. The MCP servers will be automatically loaded from `.cursor/mcp.json`",
    "",
    "For detailed integration information, see `docs/INTEGRATIONS.md`.",
  ];

  return header.concat(toolList, footer).join("\n");
}

/**
 * Ensure directory exists for a file path
 */
function ensureDirExists(filePath: string): void {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

/**
 * Write all workspace configuration files
 */
export function writeWorkspaceFiles(
  root: string,
  selectedTools: Tool[],
  options: BuildOptions = {},
  withReadme: boolean = false
): { mcpJson: string; envExample: string; integrationsMd: string } {
  const mcpJson = JSON.stringify(buildMcpJson(selectedTools, options), null, 2);
  const envExample = buildEnvExample(selectedTools);
  const integrationsMd = buildIntegrationsMd(selectedTools);

  const files: [string, string][] = [
    [path.join(root, ".cursor", "mcp.json"), mcpJson],
    [path.join(root, "env", ".env.example"), envExample],
    [path.join(root, "docs", "INTEGRATIONS.md"), integrationsMd],
  ];

  if (withReadme) {
    const readmeMd = buildReadmeMd(selectedTools);
    files.push([path.join(root, "README.md"), readmeMd]);
  }

  for (const [filePath, content] of files) {
    ensureDirExists(filePath);
    fs.writeFileSync(filePath, content, "utf8");
  }

  return { mcpJson, envExample, integrationsMd };
}

// CLI Help
function printHelp(): void {
  console.log(`
WorkspaceAlberta Generator - Create Cursor workspaces with MCP servers

Usage:
  npx ts-node generator/generator.ts [options] <tool_id> [tool_id ...]

Options:
  --list                          List all available tool IDs
  --openapi-wrapper-cmd <cmd>     Command for OpenAPI wrapper (default: "npx")
  --openapi-wrapper-args <args>   Comma-separated args for OpenAPI wrapper
  --out <path>                    Output root directory (default: current directory)
  --with-readme                   Generate a README.md stub
  --dry-run                       Print generated files without writing
  --help                          Show this help message

Examples:
  # Generate workspace for Google Drive, Slack, GitHub
  npx ts-node generator/generator.ts google_drive slack github

  # List all available tools
  npx ts-node generator/generator.ts --list

  # Dry run to preview generated files
  npx ts-node generator/generator.ts --dry-run google_drive slack

  # Generate with README
  npx ts-node generator/generator.ts --with-readme --out ./my-workspace google_drive slack
`);
}

/**
 * List all tools grouped by category
 */
function listTools(catalog: Tool[]): void {
  console.log("\nAvailable Tools:\n");

  const byCategory = new Map<string, Tool[]>();
  for (const tool of catalog) {
    if (!byCategory.has(tool.category)) {
      byCategory.set(tool.category, []);
    }
    byCategory.get(tool.category)!.push(tool);
  }

  for (const [category, tools] of Array.from(byCategory.entries()).sort()) {
    console.log(`\n${category}:`);
    for (const tool of tools.sort((a, b) =>
      a.display_name.localeCompare(b.display_name)
    )) {
      console.log(`  ${tool.id.padEnd(25)} - ${tool.display_name}`);
    }
  }

  console.log(`\nTotal: ${catalog.length} tools\n`);
}

// Main CLI
if (require.main === module) {
  const argv = minimist(process.argv.slice(2), {
    string: ["openapi-wrapper-cmd", "openapi-wrapper-args", "out"],
    boolean: ["list", "with-readme", "dry-run", "help"],
    alias: { h: "help", o: "out" },
  });

  if (argv.help) {
    printHelp();
    process.exit(0);
  }

  const catalog = loadCatalog();

  if (argv.list) {
    listTools(catalog);
    process.exit(0);
  }

  const toolIds = argv._ as string[];
  if (toolIds.length === 0) {
    console.error("Error: No tool IDs specified\n");
    printHelp();
    process.exit(1);
  }

  let selected: Tool[];
  try {
    selected = selectTools(catalog, toolIds);
  } catch (error) {
    console.error(`Error: ${(error as Error).message}`);
    console.error("\nUse --list to see all available tool IDs");
    process.exit(1);
  }

  const options: BuildOptions = {};
  if (argv["openapi-wrapper-cmd"]) {
    options.openapiWrapperCommand = argv["openapi-wrapper-cmd"];
  }
  if (argv["openapi-wrapper-args"]) {
    options.openapiWrapperArgs = argv["openapi-wrapper-args"].split(",");
  }

  const outputRoot = argv.out || process.cwd();
  const withReadme = argv["with-readme"] || false;
  const dryRun = argv["dry-run"] || false;

  if (dryRun) {
    console.log("=== DRY RUN MODE - No files will be written ===\n");

    const mcpJson = JSON.stringify(buildMcpJson(selected, options), null, 2);
    const envExample = buildEnvExample(selected);
    const integrationsMd = buildIntegrationsMd(selected);

    console.log("=== .cursor/mcp.json ===");
    console.log(mcpJson);
    console.log("\n=== env/.env.example ===");
    console.log(envExample);
    console.log("\n=== docs/INTEGRATIONS.md ===");
    console.log(integrationsMd);

    if (withReadme) {
      const readmeMd = buildReadmeMd(selected);
      console.log("\n=== README.md ===");
      console.log(readmeMd);
    }

    console.log(`\n=== Summary ===`);
    console.log(`Selected tools: ${toolIds.join(", ")}`);
    console.log(`Output directory: ${outputRoot}`);
  } else {
    writeWorkspaceFiles(outputRoot, selected, options, withReadme);

    const files = [".cursor/mcp.json", "env/.env.example", "docs/INTEGRATIONS.md"];
    if (withReadme) files.push("README.md");

    console.log(`✓ Generated workspace configuration for tools: ${toolIds.join(", ")}`);
    console.log(`✓ Output directory: ${outputRoot}`);
    console.log(`✓ Files created:`);
    files.forEach((f) => console.log(`  - ${f}`));
  }
}
