import { CLIENT_NAME, CLIENT_VERSION } from "./branding.mjs";

const PROTOCOL_VERSION = "2025-03-26";

function assertHttpUrl(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`Invalid MCP URL: ${url}`);
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("MCP URL must be http or https");
  }
  return parsed;
}

function parseSseJsonRpc(text) {
  const blocks = text.split(/\n\n+/);
  for (const block of blocks) {
    const dataLines = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .filter(Boolean);
    if (!dataLines.length) {
      continue;
    }
    return JSON.parse(dataLines.join("\n"));
  }
  throw new Error("Streamable HTTP SSE response had no JSON-RPC data");
}

export async function mcpRequest(url, body, options = {}) {
  assertHttpUrl(url);
  const headers = {
    Accept: "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": PROTOCOL_VERSION,
  };
  if (options.authorization) {
    headers.Authorization = options.authorization;
  }

  const payload = { jsonrpc: "2.0", ...body };
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(
      `MCP HTTP ${response.status} from ${url}${detail ? `: ${detail.slice(0, 240)}` : ""}`,
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const message = contentType.includes("text/event-stream")
    ? parseSseJsonRpc(await response.text())
    : await response.json();

  if (message && message.error) {
    const err = message.error;
    throw new Error(err.message || `MCP error ${err.code || ""}`.trim());
  }
  return message ? message.result : undefined;
}

export async function handshake(url, options = {}) {
  const initialize = await mcpRequest(
    url,
    {
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: { name: CLIENT_NAME, version: CLIENT_VERSION },
      },
    },
    options,
  );

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      await mcpRequest(
        url,
        { method: "notifications/initialized", params: {} },
        { ...options, signal: controller.signal },
      );
    } finally {
      clearTimeout(timer);
    }
  } catch {
    // Stateless JSON servers may ignore the initialized notification.
  }

  const listed = await mcpRequest(
    url,
    { id: 2, method: "tools/list" },
    options,
  );

  return {
    ok: true,
    protocolVersion: initialize?.protocolVersion || PROTOCOL_VERSION,
    serverInfo: initialize?.serverInfo || {},
    tools: listed?.tools || [],
  };
}

export async function callTool(url, name, args = {}, options = {}) {
  const result = await mcpRequest(
    url,
    {
      id: 3,
      method: "tools/call",
      params: { name, arguments: args },
    },
    options,
  );
  return result;
}
