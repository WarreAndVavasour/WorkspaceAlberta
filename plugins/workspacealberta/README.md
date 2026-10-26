# workspaceAlberta

Wouldn't it be great if the companies doing the work could find the public work that fits them?
workspaceAlberta helps any Canadian business find and assess tenders from the full CanadaBuys
and Alberta Purchasing Connection (APC) catalogues. Steel, lumber, aluminum, and construction
are examples, not a limit. It amplifies their judgment; it does not submit bids, contact buyers,
guarantee awards, or decide funding eligibility.

## What the plugin contains

- **The `procurement` skill** (`skills/procurement/SKILL.md`): how to search tenders for any
  business, match them across the full catalogues, read closing dates as reported, surface
  Buy Canadian signals, and present evidence and uncertainty.
- **The requirements board template** (`skills/procurement/requirements-board.html`): after the
  `classify_tender` tool returns its JSON (schema `wa.tender_requirements.v1`), Claude fills this
  self-contained page with the result. It shows the tender's requirements as a graph, a
  start-by timeline counted back from the closing time, and a checklist. The page loads only
  Google Fonts from outside; the data stays inside the page.
- **One MCP server reference** (`.mcp.json`): the hosted workspaceAlberta server at
  `https://elbowsupknivesout.warreandvavasour.com/mcp`, the same server as the workspaceAlberta
  connector.

## What it runs, sends and fetches

The plugin runs no local code, hooks or scripts. All tools run on the hosted workspaceAlberta
server. Search, deadlines, matching and daily briefs are free and need no account. Saving a
business profile needs a free sign-in. Watchlists, bid/no-bid scorecards, bid-room processing,
tender classification and contract analysis need sign-in and an active Pro subscription;
sign-in happens through your app's normal OAuth flow, and the plugin never asks for credentials.

Supply-fit search can send a business description and a short notice summary to TypeSafe AI.
Some Pro tools send tender documents or clause text to processors that the server's privacy
notice lists (TypeSafe AI, Cohere, E2B). APC documents are uploaded by you through a private,
expiring upload link. See the [privacy notice](https://elbowsupknivesout.warreandvavasour.com/privacy)
and [support page](https://elbowsupknivesout.warreandvavasour.com/support).

## Manifests

Claude reads only `.claude-plugin/plugin.json`. The root `plugin.json` (and `mcp.json`) follow the
[agent-plugins.org](https://agent-plugins.org) format and are used to build the workspaceAlberta
OpenAI plugin package (`scripts/openai_plugin.py`); Claude ignores them. Keep the `version` in both
manifests in sync.

## License

Apache-2.0. Published by Warre & Vavasour, Bow Valley, Alberta.
