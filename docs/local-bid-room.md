# Local bid room

Review APC tender documents that are already on this machine, without a public
copy. Pairs with the APC connector in
[workspacealberta-harness](https://github.com/WarreAndVavasour/workspacealberta-harness/tree/workspace-alberta/integrations/apc),
which signs in through the user's own browser session and saves each posting under
`$WA_APC_HOME/opportunities/<AB-reference>/` with a `manifest.json` receipt.

## Flow

1. Download with the connector ("Connect APC", then "Download the documents for AB-…").
2. Run the local bid room on the same machine:

```bash
export WA_APC_HOME=/media/ssd/workspacealberta/apc   # wherever the connector saved it
python -m procurement_core.local_bid_room AB-2026-06523 --check              # verify only, no sandbox
python -m procurement_core.local_bid_room AB-2026-06523 --context "What we do"
```

Or call `process_local_bid_room` from the **stdio** MCP server (`mcp-servers/canadabuys/server.py`).
It takes only an APC reference, business context and an attachment limit.

## What it does

- Reads the receipt, keeps only each file's *name* inside the reference folder (a moved or
  remounted drive still works; a crafted path cannot escape), and re-checks size, SHA-256 and
  file signature. Changed, missing or fake files are listed with a reason and never uploaded.
- Never reads `browser-profile/` or `pending.json`, never signs in, never downloads.
- Fetches APC's public notice when online and warns if its document count differs from the
  download (amendments since download). Without the notice, coverage is at most `partial`.
- Uploads up to five verified files straight into a fresh E2B sandbox; the sandbox re-hashes
  them and runs the same processor, coverage rules and Cohere review as `process_bid_room`.

## Boundaries

- Stdio and CLI only. It is deliberately absent from the shared tool list, so the hosted HTTP
  server can never read its own filesystem for a caller.
- Uses the caller's own `E2B_API_KEY` and `COHERE_API_KEY`; there is no Pro gate on a local install.
- Documents go to E2B and their contents to Cohere. Check the posting's terms first.
- An incomplete download, an attachment limit, a rejected file or a missing notice keeps
  coverage `partial`. That is not a complete RFP review.

Tests: `python -m unittest tests.test_local_bid_room` (offline; the real sandbox processor runs
against generated PDFs).
