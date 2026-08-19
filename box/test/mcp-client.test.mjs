import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";

import { callTool, handshake } from "../src/mcp-client.mjs";

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve(`http://127.0.0.1:${port}/mcp`);
    });
  });
}

function close(server) {
  return new Promise((resolve) => server.close(resolve));
}

test("handshake initialize + tools/list against a Streamable HTTP JSON server", async () => {
  const seen = [];
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      seen.push(body.method);
      let result;
      if (body.method === "initialize") {
        result = {
          protocolVersion: "2025-03-26",
          capabilities: {},
          serverInfo: { name: "canadabuys", version: "0.4.0" },
        };
      } else if (body.method === "tools/list") {
        result = {
          tools: [
            { name: "search_opportunities", description: "unified search" },
            { name: "get_my_profile", description: "saved profile" },
          ],
        };
      } else {
        result = {};
      }
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ jsonrpc: "2.0", id: body.id ?? null, result }));
    });
  });

  const url = await listen(server);
  try {
    const result = await handshake(url);
    assert.equal(result.ok, true);
    assert.equal(result.serverInfo.name, "canadabuys");
    assert.deepEqual(
      result.tools.map((tool) => tool.name),
      ["search_opportunities", "get_my_profile"],
    );
    assert.ok(seen.includes("initialize"));
    assert.ok(seen.includes("tools/list"));
  } finally {
    await close(server);
  }
});

test("callTool posts tools/call", async () => {
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      assert.equal(body.method, "tools/call");
      assert.equal(body.params.name, "get_my_profile");
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(
        JSON.stringify({
          jsonrpc: "2.0",
          id: body.id,
          result: { content: [{ type: "text", text: "No profile saved." }] },
        }),
      );
    });
  });

  const url = await listen(server);
  try {
    const result = await callTool(url, "get_my_profile", {});
    assert.equal(result.content[0].text, "No profile saved.");
  } finally {
    await close(server);
  }
});
