import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ABOUT_BODY, ABOUT_TITLE, APP_NAME, APP_SHORT_NAME, VENDOR } from "./branding.mjs";
import { defaultConfig, mcpPresets } from "./config.mjs";
import { callTool, handshake } from "./mcp-client.mjs";
import { checkForUpdates } from "./update-check.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const UI_DIR = path.join(ROOT, "ui");
const ICONS_DIR = path.join(ROOT, "icons");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".json": "application/json; charset=utf-8",
};

function sendJson(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
    "Cache-Control": "no-store",
  });
  response.end(payload);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      if (!chunks.length) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch (error) {
        reject(error);
      }
    });
    request.on("error", reject);
  });
}

function safeFile(root, requestPath) {
  const relative = requestPath.replace(/^\/+/, "") || "index.html";
  const resolved = path.resolve(root, relative);
  if (!resolved.startsWith(root)) {
    return null;
  }
  return resolved;
}

function serveStatic(response, filePath) {
  if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    response.writeHead(404).end("Not found");
    return;
  }
  const ext = path.extname(filePath);
  response.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
  fs.createReadStream(filePath).pipe(response);
}

export function createUiServer(options = {}) {
  const config = { ...defaultConfig(), ...options };

  return http.createServer(async (request, response) => {
    const url = new URL(request.url, "http://127.0.0.1");

    try {
      if (request.method === "GET" && url.pathname === "/api/about") {
        sendJson(response, 200, {
          title: ABOUT_TITLE,
          name: APP_NAME,
          shortName: APP_SHORT_NAME,
          vendor: VENDOR,
          body: ABOUT_BODY,
        });
        return;
      }

      if (request.method === "GET" && url.pathname === "/api/config") {
        sendJson(response, 200, {
          mcpUrl: config.mcpUrl,
          presets: mcpPresets(),
          provider: config.provider,
          updates: {
            enabled: Boolean(config.updates?.enabled),
            releasesPageUrl: config.updates?.releasesPageUrl,
          },
        });
        return;
      }

      if (request.method === "GET" && url.pathname === "/api/updates") {
        sendJson(response, 200, await checkForUpdates(config));
        return;
      }

      if (request.method === "POST" && url.pathname === "/api/handshake") {
        const body = await readJson(request);
        const mcpUrl = body.url || config.mcpUrl;
        sendJson(response, 200, await handshake(mcpUrl));
        return;
      }

      if (request.method === "POST" && url.pathname === "/api/tools/call") {
        const body = await readJson(request);
        const mcpUrl = body.url || config.mcpUrl;
        sendJson(
          response,
          200,
          await callTool(mcpUrl, body.name, body.arguments || {}),
        );
        return;
      }

      if (request.method === "GET" && url.pathname.startsWith("/icons/")) {
        serveStatic(response, safeFile(ICONS_DIR, url.pathname.slice("/icons/".length)));
        return;
      }

      if (request.method === "GET") {
        const relative = url.pathname === "/" ? "index.html" : url.pathname;
        serveStatic(response, safeFile(UI_DIR, relative));
        return;
      }

      response.writeHead(405).end("Method not allowed");
    } catch (error) {
      sendJson(response, 500, { ok: false, error: error.message });
    }
  });
}

export function startUiServer(options = {}) {
  const requestedPort =
    options.port == null ? defaultConfig().uiPort : Number(options.port);
  const server = createUiServer(options);
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(requestedPort, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : requestedPort;
      resolve({
        server,
        port,
        url: `http://127.0.0.1:${port}/`,
      });
    });
  });
}
