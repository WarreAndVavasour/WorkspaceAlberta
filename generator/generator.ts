import fs from "fs";
import path from "path";

type McpType = "node" | "python" | "http" | "http_openapi";

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
  integration_status: "native" | "openapi" | "proxy" | "hosted";
  mcp: McpConfig;
}

export interface BuildOptions {
  openapiWrapperCommand?: string;
  openapiWrapperArgs?: string[];
}

export interface GeneratedFiles {
  mcpJson: string;
  envExample: string;
  integrationsMd: string;
}

const DEFAULT_CATALOG_PATH = path.join(__dirname, "catalog.json");
const DEFAULT_OPENAPI_WRAPPER_COMMAND = "npx";
const DEFAULT_OPENAPI_WRAPPER_ARGS = ["-y", "your-openapi-mcp-wrapper"];

export function loadCatalog(catalogPath: string = DEFAULT_CATALOG_PATH): Tool[] {
  const data = fs.readFileSync(catalogPath, "utf8");
  return JSON.parse(data);
}

export function selectTools(catalog: Tool[], selectedIds: string[]): Tool[] {
  const byId = new Map(catalog.map((tool) => [tool.id, tool]));
  const missing = selectedIds.filter((id) => !byId.has(id));

  if (missing.length) {
    throw new Error(`Unknown tool ids: ${missing.join(", ")}`);
  }

  return selectedIds.map((id) => byId.get(id)!);
}

function envVarsToMap(envVars: EnvVar[]): Record<string, string> {
  return Object.fromEntries(envVars.map((v) => [v.name, `\${env:${v.name}}`]));
}

export function buildMcpJson(
  selectedTools: Tool[],
  options: BuildOptions = {}
): Record<string, unknown> {
  const servers: Record<string, unknown> = {};

  for (const tool of selectedTools) {
    const m = tool.mcp;

    if (m.type === "node" || m.type === "python") {
      servers[m.server_name] = {
        command: m.command,
        args: m.args,
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
        m.openapi_url ??
        (m.openapi_url_env ? `\${env:${m.openapi_url_env}}` : undefined);

      if (!spec) {
        throw new Error(
          `Tool ${tool.id} is http_openapi but missing openapi_url/openapi_url_env`
        );
      }

      servers[m.server_name] = {
        command: options.openapiWrapperCommand ?? DEFAULT_OPENAPI_WRAPPER_COMMAND,
        args: options.openapiWrapperArgs ?? DEFAULT_OPENAPI_WRAPPER_ARGS,
        env: {
          OPENAPI_SPEC_URL: spec,
          ...envVarsToMap(m.env_vars),
        },
      };
    }
  }

  return { servers };
}

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

function ensureDirExists(filePath: string) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

export function writeWorkspaceFiles(
  root: string,
  selectedTools: Tool[],
  options: BuildOptions = {}
): GeneratedFiles {
  const mcpJson = JSON.stringify(buildMcpJson(selectedTools, options), null, 2);
  const envExample = buildEnvExample(selectedTools);
  const integrationsMd = buildIntegrationsMd(selectedTools);

  const files: [string, string][] = [
    [path.join(root, ".cursor", "mcp.json"), mcpJson],
    [path.join(root, "env", ".env.example"), envExample],
    [path.join(root, "docs", "INTEGRATIONS.md"), integrationsMd],
  ];

  for (const [filePath, content] of files) {
    ensureDirExists(filePath);
    fs.writeFileSync(filePath, content, "utf8");
  }

  return { mcpJson, envExample, integrationsMd };
}

if (require.main === module) {
  const [, , ...ids] = process.argv;
  if (!ids.length) {
    console.error(
      "Usage: ts-node generator.ts <tool_id> [tool_id ...]\nExample: ts-node generator.ts google_drive slack github stripe"
    );
    process.exit(1);
  }

  const catalog = loadCatalog();
  const selected = selectTools(catalog, ids);
  writeWorkspaceFiles(process.cwd(), selected);
  console.log(
    `Generated .cursor/mcp.json, env/.env.example, docs/INTEGRATIONS.md for tools: ${ids.join(
      ", "
    )}`
  );
}
