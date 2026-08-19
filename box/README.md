# WorkspaceAlberta Box

A stripped desktop harness for WorkspaceAlberta. Product of **Warre & Vavasour**.

This is a clean box: official MCP in, procurement tools out. It is **not** official DeepSeek software, does not use DeepSeek branding, and does not call China update or download hosts.

Official DSH and other tools get added later. GBrain stays out of this box. The Raspberry Pi / official DSH harness design is unchanged.

## What it is

- **App name:** WorkspaceAlberta Box (WA Box)
- **MCP client:** Streamable HTTP JSON-RPC, the same protocol the repo's `server_http.py` adapter already speaks
- **Default connection:** local `http://127.0.0.1:8000/mcp`
- **Documented hosted URL:** `https://elbowsupknivesout.warreandvavasour.com/mcp` (public browse; no invented CanadaBuys credential)
- **Model provider:** empty / user-configured OpenAI-compatible slot. First run is the MCP connection, not a vendor API-key prompt
- **Updates:** off. The only placeholder, if you turn them on, is GitHub Releases for `HarleyCoops/WorkspaceAlberta`

This package is a greenfield client. It does not vendor the community DeepSeek Harness desktop.

## How to run

From the repo root, start the local WorkspaceAlberta MCP server:

```
python -m pip install -r requirements.txt
python mcp-servers/canadabuys/server_http.py
```

That serves Streamable HTTP MCP at `http://127.0.0.1:8000/mcp`.

In another terminal:

```
cd box
npm start
```

Open `http://127.0.0.1:8787/` and click **Connect**. The box handshakes (`initialize` + `tools/list`) and lists the procurement tools.

Handshake only (no UI):

```
cd box
npm run handshake
```

Optional native window (downloads Electron on first use, not required):

```
cd box
npm run desktop
```

Window title, tray label, and About panel are **WorkspaceAlberta Box**. There is no installer in this first package; when one is added it will use the same name.

## How MCP connects

1. Box POSTs official JSON-RPC to the `/mcp` URL (`initialize`, then `tools/list`, then `tools/call`).
2. The local adapter is `mcp-servers/canadabuys/server_http.py`. The procurement logic stays in `procurement_core/`. This client does not reimplement CanadaBuys.
3. Override the URL with `WA_BOX_MCP_URL` or `--url`.

```
cd box
node src/cli.mjs handshake --url http://127.0.0.1:8000/mcp
node src/cli.mjs call get_my_profile --url http://127.0.0.1:8000/mcp
```

Hosted endpoint (same tools, no local Python process):

```
node src/cli.mjs handshake --url https://elbowsupknivesout.warreandvavasour.com/mcp
```

## Tests

From the repo root:

```
python -m unittest tests.test_box_source_guard tests.test_box_mcp_handshake
```

From `box/`:

```
npm test
```

`tests.test_box_source_guard` fails if the known China update/download hosts or the default vendor API host reappear in shipped Box source. `tests.test_box_mcp_handshake` starts the local WA HTTP server and records a real initialize / tools-list handshake through this client.

## Later, not now

- Official DSH plugin chrome
- Extra business-tool catalog
- Hardware / copper mounting
- Auto-download installers
