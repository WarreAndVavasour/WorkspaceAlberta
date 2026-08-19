#!/usr/bin/env node
import { ABOUT_BODY, ABOUT_TITLE, APP_NAME, VENDOR } from "./branding.mjs";
import { defaultConfig } from "./config.mjs";
import { callTool, handshake } from "./mcp-client.mjs";
import { startUiServer } from "./ui-server.mjs";

function argValue(flag, fallback) {
  const index = process.argv.indexOf(flag);
  if (index === -1 || index === process.argv.length - 1) {
    return fallback;
  }
  return process.argv[index + 1];
}

function printAbout() {
  process.stdout.write(`${ABOUT_TITLE}\n${ABOUT_BODY}\nVendor: ${VENDOR}\n`);
}

async function runHandshake() {
  const config = defaultConfig();
  const url = argValue("--url", config.mcpUrl);
  const result = await handshake(url);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

async function runCall() {
  const config = defaultConfig();
  const url = argValue("--url", config.mcpUrl);
  const name = process.argv[3];
  if (!name || name.startsWith("--")) {
    throw new Error("Usage: wa-box call <tool> [--url URL] [--args JSON]");
  }
  const args = JSON.parse(argValue("--args", "{}"));
  const result = await callTool(url, name, args);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

async function runServe() {
  const config = defaultConfig();
  const port = Number(argValue("--port", config.uiPort));
  const { url } = await startUiServer({ port, mcpUrl: config.mcpUrl });
  process.stdout.write(`${APP_NAME} UI: ${url}\n`);
  process.stdout.write(`Default MCP: ${config.mcpUrl}\n`);
  process.stdout.write("Start the local WA server first:\n");
  process.stdout.write("  python mcp-servers/canadabuys/server_http.py\n");
  if (process.argv.includes("--open")) {
    const { default: opener } = await import("node:child_process");
    const start =
      process.platform === "darwin"
        ? "open"
        : process.platform === "win32"
          ? "start"
          : "xdg-open";
    opener.spawn(start, [url], { detached: true, shell: process.platform === "win32" });
  }
}

const command = process.argv[2] || "serve";

const commands = {
  about: printAbout,
  handshake: runHandshake,
  call: runCall,
  serve: runServe,
};

if (!commands[command]) {
  process.stderr.write(
    `Usage: node src/cli.mjs <about|handshake|call|serve> [options]\n`,
  );
  process.exit(2);
}

commands[command]().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
