# procurement_core

The engine. Pure Python, no MCP dependency — every adapter (stdio MCP, StreamableHTTP MCP, REST) dispatches into this package, so tool behaviour is defined exactly once.

| File | Role |
|---|---|
| `service.py` | All 21 tool handlers, `TOOL_NAMES` registry, `call_tool_text()` dispatch, CanadaBuys CSV client + cache, Alberta APC API client, unified normalizer, deterministic profile scoring, Cohere model routing with key failover |
| `fixtures.py` | Offline CanadaBuys CSV + APC JSON ingest when `PROCUREMENT_FIXTURE_DIR` is set (tests only; hosted MCP stays live) |
| `e2b_bid_room.py` | E2B sandbox bid-room processing: payload builders, self-contained sandbox processor script, Cohere Parse document layer, in-sandbox Command A+ review, artifact validation and rendering |
| `requirements/` | `classify_tender`: PyMuPDF split of tender PDFs into clauses (`extract.py`), the child-process runner and worker that do the parsing (`child.py`, `extract_worker.py`), the requirement tag library (`tags.py`), TypeSafe Jev questions and stdlib client (`jev.py`), and the bounded L0 → pages → L1 → merge pipeline with markdown rendering (`pipeline.py`). Shared with `pipelines/requirement_classifier/` |
| `cohere_parse.py` | Official Cohere Parse helpers (`POST /v2/parse`, `parse-v5.0`, `image_url` documents only). Injected into the sandbox processor; unit-tested with a mocked HTTP call |

## Contract for adding a tool

1. Declare schema in `mcp-servers/canadabuys/mcp_tools.py`
2. Implement `async def <tool_name>(args: dict) -> str` in `service.py` (return markdown)
3. Add the name to `TOOL_NAMES` (dispatch resolves handlers by name via `globals()`)
4. Test it in `tests/`

## Principles

- Deterministic logic first. Cohere Parse is the bid-room document layer (PDF/image → markdown). Command A+ is only for judgment tools.
- Sources degrade independently — a failing upstream produces a warning line, not a failed tool call.
- Untrusted tender attachments are never parsed in the service process. `process_bid_room` opens them inside an E2B sandbox (a separate VM) with hard size/count/timeout limits. `classify_tender` reads PDF text with PyMuPDF in a separate OS process inside the same Cloud Run container (`requirements/child.py` runs `requirements/extract_worker.py`): isolated Python (`-I -B`), no secrets in its environment, its own process group, CPU time, 1.5 GB address-space, zero file-size and no-core-dump limits, and a wall-clock timeout of at most 60 s per file, after which the whole process group is killed. It is not a sandbox VM: the child shares the container's filesystem and network. PDFs only, 25 MB per file, at most 2 files parsed at once, 800 pages and 8,000 clauses per call.
- User-provided integers are clamped (`clamp_int`), never trusted.

Full details: `docs/architecture.md` and `docs/mcp-tool-reference.md`.
