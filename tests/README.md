# tests

| File | Covers |
|---|---|
| `test_canadabuys_mcp_smoke.py` | Stdio MCP server startup and tool-list/response smoke test — run this after any change to the server, config, or agent setup |
| `test_procurement_http_app.py` | Hosted FastAPI app: routes, tool dispatch, error envelopes |
| `test_e2b_bid_room.py` | Bid-room payload builders, artifact parsing/validation, markdown rendering (no live sandbox) |

Run everything:

```bash
python -m unittest discover tests
```

Run the canonical smoke test only:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

Tests avoid live network calls to CanadaBuys/APC/Cohere/E2B; live-path smoke scripts live in `scripts/` (e.g. `e2b_bid_room_smoke.py`).
