# procurement_core

The engine. Pure Python, no MCP dependency — every adapter (stdio MCP, StreamableHTTP MCP, REST) dispatches into this package, so tool behaviour is defined exactly once.

| File | Role |
|---|---|
| `service.py` | All 21 tool handlers, `TOOL_NAMES` registry, `call_tool_text()` dispatch, CanadaBuys CSV client + cache, Alberta APC API client, unified normalizer, deterministic profile scoring, Cohere model routing with key failover |
| `fixtures.py` | Offline CanadaBuys CSV + APC JSON ingest when `PROCUREMENT_FIXTURE_DIR` is set (tests only; hosted MCP stays live) |
| `e2b_bid_room.py` | E2B sandbox bid-room processing: payload builders, self-contained sandbox processor script, Cohere Parse document layer, in-sandbox Command A+ review, artifact validation and rendering |
| `cohere_parse.py` | Official Cohere Parse helpers (`POST /v2/parse`, `parse-v5.0`, `image_url` documents only). Injected into the sandbox processor; unit-tested with a mocked HTTP call |

## Contract for adding a tool

1. Declare schema in `mcp-servers/canadabuys/mcp_tools.py`
2. Implement `async def <tool_name>(args: dict) -> str` in `service.py` (return markdown)
3. Add the name to `TOOL_NAMES` (dispatch resolves handlers by name via `globals()`)
4. Test it in `tests/`

## Principles

- Deterministic logic first. Cohere Parse is the bid-room document layer (PDF/image → markdown). Command A+ is only for judgment tools.
- Sources degrade independently — a failing upstream produces a warning line, not a failed tool call.
- Untrusted tender attachments are only ever opened inside an E2B sandbox with hard size/count/timeout limits.
- User-provided integers are clamped (`clamp_int`), never trusted.

Full details: `docs/architecture.md` and `docs/mcp-tool-reference.md`.
