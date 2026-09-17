# WorkspaceAlberta Pipeline Demos

Three standalone pipelines against the live stack. No Composio, no SDKs beyond
`e2b` — every demo runs from a bare Python 3 install plus the repo venv.

| Demo | Pipeline | Needs |
|---|---|---|
| `demo1_daily_brief.py` | workspacealberta MCP `daily_bid_brief` → markdown brief → `/data/tasks` shared workspace | nothing (keyless, public endpoint) |
| `demo2_tender_extract.py` | tender PDF URL → E2B sandbox download → text extraction → evidence artifact + report | `E2B_API_KEY` in repo `.env`; add `COHERE_API_KEY` for the full analysis stage |
| `demo3_match_shortlist.py` | `find_matching_opportunities` against a business profile → geo-filter to the Rocky Mountain House drive ring | nothing (keyless) |

## Run

```sh
python3 demos/demo1_daily_brief.py
.venv/bin/python demos/demo2_tender_extract.py [pdf-url] [reference] [title]
python3 demos/demo3_match_shortlist.py
```

Outputs land in `demos/output/` and mirror into `/data/tasks/{from-zcode,from-grok}/`
so any platform client (ZCode, Grok Bot via the `wa-tasks` MCP server) sees them.

## Notes

- `wa_mcp.py` is a dependency-free Streamable-HTTP MCP client. Cloudflare's WAF
  on the endpoint rejects the default Python-urllib User-Agent — the helper sends
  a custom one.
- The public endpoint treats business profiles as per-call. Persistent profiles,
  the watchlist, `process_bid_room`, and `analyze_contract_with_cohere` unlock
  with a `wa_live_` subscriber key (see `docs/pricing-and-subscription.md`).
- Demo 2 auto-upgrades to the full chain (Cohere fit score, risks, deadlines,
  questions-to-ask) the moment `COHERE_API_KEY` appears in `.env`.
