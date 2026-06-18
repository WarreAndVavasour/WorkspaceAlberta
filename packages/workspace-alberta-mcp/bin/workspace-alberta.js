#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createRequire } from "node:module";

const DEFAULT_ENDPOINT = "https://workspacealberta-719334491060.northamerica-northeast1.run.app/mcp";
const require = createRequire(import.meta.url);

function printHelp() {
  console.log(`WorkspaceAlberta MCP stdio bridge\n\nUsage:\n  workspace-alberta [endpoint-url] [mcp-remote options]\n\nDefault endpoint:\n  ${DEFAULT_ENDPOINT}\n\nEnvironment:\n  WORKSPACEALBERTA_MCP_URL  Override the hosted MCP endpoint.\n\nExamples:\n  npx -y @warreandvavasour/workspace-alberta\n  WORKSPACEALBERTA_MCP_URL=http://127.0.0.1:8000/mcp npx -y @warreandvavasour/workspace-alberta\n`);
}

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h")) {
  printHelp();
  process.exit(0);
}

let endpoint = process.env.WORKSPACEALBERTA_MCP_URL || DEFAULT_ENDPOINT;
let rest = argv;
if (argv[0] && /^https?:\/\//.test(argv[0])) {
  endpoint = argv[0];
  rest = argv.slice(1);
}

const proxyPath = require.resolve("mcp-remote/dist/proxy.js");
const child = spawn(process.execPath, [proxyPath, endpoint, ...rest], {
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

child.on("error", (error) => {
  console.error(`Failed to start mcp-remote: ${error.message}`);
  process.exit(1);
});
