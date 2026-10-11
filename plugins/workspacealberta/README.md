# WorkspaceAlberta

Wouldn't it be great if the companies doing the work could find the public work that fits them?
WorkspaceAlberta helps Canadian owners and teams find and assess tenders from CanadaBuys and
Alberta Purchasing Connection (APC). It amplifies their judgment; it does not submit bids,
contact buyers or guarantee awards.

## What the plugin contains

- **The `procurement` skill** (`skills/procurement/SKILL.md`): how to search tenders, match them
  to a business, read closing dates as reported, and present evidence and uncertainty.
- **The requirements board template** (`skills/procurement/requirements-board.html`): after the
  `classify_tender` tool returns its JSON (schema `wa.tender_requirements.v1`), Claude fills this
  self-contained page with the result. It shows the tender's requirements as a graph, a
  start-by timeline counted back from the closing time, and a checklist. The page loads only
  Google Fonts from outside; the data stays inside the page.
- **One MCP server reference** (`.mcp.json`): the hosted WorkspaceAlberta server at
  `https://elbowsupknivesout.warreandvavasour.com/mcp`, the same server as the WorkspaceAlberta
  connector.

## What it runs, sends and fetches

The plugin runs no local code, hooks or scripts. All tools run on the hosted WorkspaceAlberta
server. Search, deadlines, matching and daily briefs are free and need no account. Saving a
business profile needs a free sign-in. Watchlists, bid/no-bid scorecards, bid-room processing,
tender classification and contract analysis need sign-in and an active Pro subscription;
sign-in happens through your app's normal OAuth flow, and the plugin never asks for credentials.

Some Pro tools send tender documents or clause text to processors that the server's privacy
notice lists (TypeSafe AI, Cohere, E2B). APC documents are uploaded by you through a private,
expiring upload link. See the [privacy notice](https://elbowsupknivesout.warreandvavasour.com/privacy)
and [support page](https://elbowsupknivesout.warreandvavasour.com/support).

## License

Apache-2.0. Published by Warre & Vavasour, Bow Valley, Alberta.
