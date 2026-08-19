# tests

| File | Covers |
|---|---|
| `test_canadabuys_mcp_smoke.py` | Stdio MCP server startup and tool-list/response smoke test — run this after any change to the server, config, or agent setup |
| `test_procurement_fixtures.py` | Offline CanadaBuys + APC fixture ingest; shop-in-Red-Deer query returns structured rows (title, close date, source) with no network |
| `test_procurement_http_app.py` | Hosted FastAPI app: routes, tool dispatch, error envelopes |
| `test_e2b_bid_room.py` | Bid-room payload builders, artifact parsing/validation, markdown rendering (no live sandbox) |
| `test_box_source_guard.py` | Shipped Box source must not contain the known China update hosts or the default vendor API host |
| `test_box_mcp_handshake.py` | WorkspaceAlberta Box CLI initialize + tools/list against the local WA HTTP server |

Run everything:

```bash
python -m unittest discover tests
```

Run the canonical smoke test only:

```bash
python -m unittest tests.test_canadabuys_mcp_smoke
```

Run the offline fixture ingest tests (no network; uses `tests/fixtures/procurement/`):

```bash
python -m unittest tests.test_procurement_fixtures
```

Tests avoid live network calls to CanadaBuys/APC/Cohere/E2B; live-path smoke scripts live in `scripts/` (e.g. `e2b_bid_room_smoke.py`).
