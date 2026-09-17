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

## Harness mode (no ZCode)

The same pipelines run inside the workspaceAlberta harness headless, using the
harness agent + the `workspacealberta` MCP plugin instead of ZCode:

```sh
# one-time: wire the MCP server into the headless profile
cp demos/wa-headless-mcp.patch.yml ~/.dsh/profiles/headless/wa-mcp.patch.yml

# run a task; launch FROM the directory you want the harness to treat as its
# writable workspace (its file sandbox denies writes outside the boot dir)
cd /data/tasks && dsh --profile headless \
  --patch ~/.dsh/profiles/headless/wa-mcp.patch.yml \
  "Use the workspace_alberta MCP tool find_matching_opportunities ..."
```

Harness session traces (zstd JSONL) land in
`~/.dsh/sessions/<workspace-slug>/session-*/session.jsonl.zstd` — the
`tool/call` events carry the same MCP tool names and argument shapes as the
ZCode-side traces in `demos/output/traces/`, so the two runs diff cleanly.

## Demo 5 — central identity

`wa_credentials.py` implements the fleet credential convention:
`~/.config/workspacealberta/credentials` (0600) holds the business profile,
an optional `wa_live_` subscriber key, and per-platform OAuth token slots
(`--set-key`, `--set-platform`, `--show`). Demo 5 reads that one store and
auto-fills a bid form against the newest E2B artifact — the same identity
every platform client (ZCode, Grok Bot, harness, mobile) should share.

## Harness batch

`harness_batch.py` runs all 12 simulated businesses through `dsh --profile
headless` in parallel (launches from /data/tasks so the harness sandbox can
write the shared workspace). 12/12 in 114s at 4 workers on a Pi 5.
