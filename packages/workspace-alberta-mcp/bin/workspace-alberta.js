#!/usr/bin/env node
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const DEFAULT_ENDPOINT = "https://elbowsupknivesout.warreandvavasour.com/mcp";
const CREDENTIALS_PATH = join(homedir(), ".config", "workspacealberta", "credentials");
const require = createRequire(import.meta.url);

function printHelp() {
  console.log(`WorkspaceAlberta MCP stdio bridge

Usage:
  workspace-alberta [endpoint-url] [mcp-remote options]

Default endpoint:
  ${DEFAULT_ENDPOINT}

Environment:
  WORKSPACEALBERTA_MCP_URL  Override the hosted MCP endpoint.
  WORKSPACEALBERTA_API_KEY  Pro subscriber key (wa_live_...). Sent as an
                            Authorization: Bearer header so the six Pro tools
                            are available. Free tools work without it.

Credentials file:
  ${CREDENTIALS_PATH}
  Read when WORKSPACEALBERTA_API_KEY is unset. Written by
  installer/configure-subscriber-key.sh on provisioned terminals.

Examples:
  npx -y @warreandvavasour/workspace-alberta
  WORKSPACEALBERTA_API_KEY=wa_live_... npx -y @warreandvavasour/workspace-alberta
  WORKSPACEALBERTA_MCP_URL=http://127.0.0.1:8000/mcp npx -y @warreandvavasour/workspace-alberta
`);
}

/**
 * Read a KEY=value pair out of the provisioned credentials file.
 *
 * A missing or unreadable file is the normal case for a free-tier user, so it
 * degrades to null rather than warning.
 */
function readCredential(name) {
  let contents;
  try {
    contents = readFileSync(CREDENTIALS_PATH, "utf8");
  } catch {
    return null;
  }
  for (const line of contents.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;
    if (trimmed.slice(0, separator).trim() === name) {
      return trimmed.slice(separator + 1).trim() || null;
    }
  }
  return null;
}

const argv = process.argv.slice(2);
if (argv.includes("--help") || argv.includes("-h")) {
  printHelp();
  process.exit(0);
}

let endpoint =
  process.env.WORKSPACEALBERTA_MCP_URL || readCredential("WA_MCP_URL") || DEFAULT_ENDPOINT;
let rest = argv;
if (argv[0] && /^https?:\/\//.test(argv[0])) {
  endpoint = argv[0];
  rest = argv.slice(1);
}

// An explicit --header on the command line always wins over the configured key.
const apiKey = process.env.WORKSPACEALBERTA_API_KEY || readCredential("WA_API_KEY");
const headerArgs = apiKey && !rest.includes("--header")
  ? ["--header", `Authorization: Bearer ${apiKey}`]
  : [];

const proxyPath = require.resolve("mcp-remote/dist/proxy.js");
const child = spawn(process.execPath, [proxyPath, endpoint, ...headerArgs, ...rest], {
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
