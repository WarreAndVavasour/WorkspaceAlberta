"""Shared helper: call the workspacealberta MCP server over Streamable HTTP.

Stdlib only - no SDK, no Composio. Works on any Python 3.9+ on any machine.
"""
import json
import urllib.request

MCP_URL = "https://elbowsupknivesout.warreandvavasour.com/mcp"

_CLIENT_INFO = {"name": "wa-demo", "version": "1.0.0"}


def _post(payload: dict) -> dict:
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            # Cloudflare's WAF blocks the default Python-urllib UA with a 403
            "User-Agent": "workspacealberta-demo/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read().decode()
    if not body.strip():
        return {}  # e.g. 202 Accepted for notifications
    # Streamable HTTP may answer as plain JSON or SSE; take the last JSON object.
    if body.lstrip().startswith("{"):
        return json.loads(body)
    for line in reversed(body.splitlines()):
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise RuntimeError(f"unparseable MCP response: {body[:200]}")


def mcp_initialize() -> dict:
    return _post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": _CLIENT_INFO},
    })


def mcp_call(tool: str, arguments: dict | None = None, req_id: int = 2) -> str:
    """Call a tool and return its first text content block."""
    _post({  # stateless server: initialize, then call directly
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": _CLIENT_INFO},
    })
    resp = _post({
        "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    })
    if "error" in resp:
        raise RuntimeError(f"MCP error: {resp['error']}")
    for block in resp["result"].get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return ""


ROCKY_RING = [
    "rocky mountain house", "clearwater county", "nordegg", "caroline",
    "sylvan lake", "red deer", "lacombe", "rimbey", "sundre",
    "drayton valley", "brazeau", "mountain view", "ponoka", "stettler",
]


def filter_local(text: str) -> list[str]:
    """Return the geography lines of a brief that fall inside the drive ring."""
    hits = []
    for line in text.splitlines():
        low = line.lower()
        if any(place in low for place in ROCKY_RING):
            hits.append(line.strip())
    return hits
