# workspaceAlberta directory submission packet

Prepared October 26, 2026. Every listing points at one endpoint:

```text
https://elbowsupknivesout.warreandvavasour.com/mcp
```

The endpoint URL stays clean. Links to the website carry
`?utm_source=<directory>&utm_medium=directory&utm_campaign=workspacealberta`
so the Agent Reach Board's People tab can attribute visits.

Already live: [Claude's connector directory](https://claude.ai/directory/connectors/workspacealberta).

## Shared listing values

Use these values everywhere unless a section says otherwise.

| Field | Value |
|---|---|
| Name | workspaceAlberta |
| Short description (100 chars max) | Search every CanadaBuys and Alberta Purchasing Connection tender. Free briefs; Pro bid-room tools. |
| One-line tagline | Find Canadian public contracts and assess your next bid. |
| MCP endpoint | `https://elbowsupknivesout.warreandvavasour.com/mcp` |
| Transport | Streamable HTTP |
| Authentication | None to connect. OAuth 2.1 (PKCE S256, CIMD or dynamic registration) when a sign-in or Pro tool returns HTTP 401. |
| Repository | `https://github.com/WarreAndVavasour/WorkspaceAlberta` |
| Website | `https://warreandvavasour.com/workspacealberta?utm_source=<directory>&utm_medium=directory&utm_campaign=workspacealberta` |
| Privacy | `https://elbowsupknivesout.warreandvavasour.com/privacy` |
| Support | `https://elbowsupknivesout.warreandvavasour.com/support` |
| Contact | `christian@warreandvavasour.com` |
| Icon (square PNG, 512x512) | `https://elbowsupknivesout.warreandvavasour.com/icon.png` |
| Icon (SVG) | `https://elbowsupknivesout.warreandvavasour.com/icon.svg` |
| Screenshot / hero | `docs/assets/women-workers-collage.png` (README hero). For a product screenshot, use `docs/assets/bid-room-owner-artifact.svg`, exported to PNG if the site rejects SVG. |
| Keywords | Canadian procurement, CanadaBuys, Alberta Purchasing Connection, government tenders, bids, trades, construction |
| Category (when asked) | Search & data / Government & public sector / Business |

Long description:

> Wouldn't it be great if the next contract was easier to find? workspaceAlberta
> connects your AI client to the full CanadaBuys and Alberta Purchasing Connection
> catalogues, for every category of work. Search open opportunities, check
> deadlines, read the source posting and rank tenders against your business, with
> Buy Canadian and other domestic-preference flags when the notice publishes them.
> Search, details, deadlines, matching and the daily bid brief are free with no
> account. Pro adds a watchlist, bid/no-bid scorecards, bid-room document review
> and tender requirement lists. It does not submit bids or contact buyers. Verify
> requirements against the official posting before bidding.

Tool counts (from the live `tools/list` and `get_server_guide`, October 26, 2026):
29 tools. 20 are public with no account. 2 need a free sign-in
(`set_business_profile`, `get_my_profile`). 7 need sign-in and Pro
(`watch_opportunity`, `list_watchlist`, `unwatch_opportunity`,
`bid_no_bid_scorecard`, `process_bid_room`, `classify_tender`,
`analyze_contract_with_cohere`). Full list: [mcp-tool-reference.md](mcp-tool-reference.md).

Example prompt for any "example usage" field:

```text
I run a small general contractor in Red Deer, Alberta.
What construction tenders close in the next 7 days?
Give me the reference, buyer, closing time and official link for each.
```

## 1. Official MCP Registry

- **Status:** Listed under the old personal namespace
  `io.github.HarleyCoops/workspace-alberta`, version 0.4.0, published July 20,
  2026, with the npm bridge package. Not yet listed under a company namespace.
- **What changed in this repo:** `server.json` now uses
  `com.warreandvavasour/workspacealberta`, version 1.3.0 (up from the registry's
  0.4.0; it matches the server release on main, which the version tests
  enforce), schema 2025-12-11 (the
  latest released schema; live registry entries use it), a current description,
  `title`, `websiteUrl` with UTM, and both icons. It validates against the
  published JSON schema.
- **npm package removed from `server.json`:** `@warreandvavasour/workspace-alberta`
  0.1.1 exists on npm (a `mcp-remote` bridge), but its `mcpName` is
  `io.github.HarleyCoops/workspace-alberta`. The registry rejects a package whose
  `mcpName` does not match the server name. Listing only the remote is the clean
  install. To bring the package back: set `mcpName` in
  `packages/workspace-alberta-mcp/package.json` to
  `com.warreandvavasour/workspacealberta`, bump to 0.1.2, `npm publish`, then
  re-add the `packages` block.

Namespace trade-off: `com.warreandvavasour/*` is tied to the company domain and
survives GitHub org renames, but needs a DNS TXT record and a private key to
publish. `io.github.WarreAndVavasour/*` needs only a GitHub login by an org
member, but ties the listing to the GitHub org name.

Steps (domain namespace):

1. Generate a key once and keep it out of the repo:

   ```bash
   mkdir -p ~/.config/mcp-publisher && chmod 700 ~/.config/mcp-publisher
   openssl genpkey -algorithm Ed25519 -out ~/.config/mcp-publisher/warreandvavasour-ed25519.pem
   chmod 600 ~/.config/mcp-publisher/warreandvavasour-ed25519.pem
   PUBLIC_KEY="$(openssl pkey -in ~/.config/mcp-publisher/warreandvavasour-ed25519.pem -pubout -outform DER | tail -c 32 | base64)"
   echo "v=MCPv1; k=ed25519; p=${PUBLIC_KEY}"
   ```

2. Add one TXT record in Cloudflare (DNS for warreandvavasour.com is on
   Cloudflare: `hayes.ns.cloudflare.com`, `kristina.ns.cloudflare.com`):

   | Type | Name | Content | TTL |
   |---|---|---|---|
   | TXT | `@` (apex, `warreandvavasour.com`) | `v=MCPv1; k=ed25519; p=<PUBLIC_KEY from step 1>` | Auto |

   The record must be on the apex, not a subdomain. Leave the existing SPF,
   DKIM and Google verification TXT records alone.

3. Check it resolved:

   ```bash
   curl -s "https://dns.google/resolve?name=warreandvavasour.com&type=TXT" | grep MCPv1
   ```

4. Install `mcp-publisher`, log in and publish from the repo root:

   ```bash
   curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher
   PRIVATE_KEY="$(openssl pkey -in ~/.config/mcp-publisher/warreandvavasour-ed25519.pem -noout -text | grep -A3 'priv:' | tail -n +2 | tr -d ' :\n')"
   ./mcp-publisher login dns --domain warreandvavasour.com --private-key "${PRIVATE_KEY}"
   ./mcp-publisher publish
   ```

5. Verify:

   ```bash
   curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=workspacealberta"
   ```

6. Optional: mark the old `io.github.HarleyCoops/workspace-alberta` entry
   deprecated so the two entries don't compete. That needs `mcp-publisher login
   github` as HarleyCoops (browser device code). Not verified which
   `mcp-publisher` subcommand sets status in the current release; check
   `./mcp-publisher --help` first.

## 2. PulseMCP

- **Status:** Not verified as listed. Submissions are paused. Their submit page
  says: "We are not accepting new MCP server or client submissions right now,
  and we are not making changes to existing listings."
- **Registry ingestion:** The same page recommends publishing to the official
  registry and says "we will pick it up automatically once we are back." So
  publishing step 1 is the submission. Nothing else to do now.
- **UTM for any later manual edit:** `utm_source=pulsemcp`.

## 3. Smithery

- **Status:** Not checked for an existing listing (search needs the site UI).
- **`smithery.yaml`:** Not needed. Smithery's external-server docs publish a
  remote server by URL and do not mention `smithery.yaml`; that file is for
  servers Smithery builds and hosts. None added.
- **Requirements we meet:** Streamable HTTP; OAuth for protected tools with a
  401 challenge (Smithery uses the 401 to detect OAuth, and registers through
  Client ID Metadata Documents, which the server supports). Public tools let the
  scan finish without signing in.
- **Steps:** Open `https://smithery.ai/new` (expect a browser sign-in; not verified), enter
  `https://elbowsupknivesout.warreandvavasour.com/mcp`, finish the flow, then
  open Settings > Verification for the official-vendor checklist. CLI
  equivalent after `smithery login`:

  ```bash
  npx @smithery/cli mcp publish "https://elbowsupknivesout.warreandvavasour.com/mcp" -n @warreandvavasour/workspacealberta
  ```

- **Fields:** Name, description, homepage, icon from Shared listing values.
  Homepage: `https://warreandvavasour.com/workspacealberta?utm_source=smithery&utm_medium=directory&utm_campaign=workspacealberta`.
- **Fallback if the scan fails:** Smithery reads a static card at
  `/.well-known/mcp/server-card.json`. We don't serve one. Only add it if the
  scan fails; that is a server change and needs its own PR and deploy.

## 4. Glama

- **Status:** Listed, but under the old owner:
  `https://glama.ai/mcp/servers/HarleyCoops/WorkspaceAlberta` ("WorkspaceAlberta
  is a Canadian procurement intelligence workspace."), plus a connector entry at
  `https://glama.ai/mcp/connectors/io.github.HarleyCoops/workspace-alberta`
  pulled from the registry. The source repo it points at
  (`HarleyCoops/WorkspaceAlberta`) now returns 404. The page says "This server
  cannot be deployed" and shows no license grade.
- **Steps:**
  1. Sign in to glama.ai with GitHub as a WarreAndVavasour org member.
  2. Use "Add Server" with `https://github.com/WarreAndVavasour/WorkspaceAlberta`,
     then "Claim" on the new entry. Ask Glama support (or use the old page's
     Claim button) to merge or retire the HarleyCoops entry.
  3. After the registry publish, the connector entry should appear as
     `com.warreandvavasour/workspacealberta`.
- **Fields:** Name, description, website
  (`utm_source=glama`), icon from Shared listing values.
- **Gap:** The repo has no LICENSE file and no GitHub description or topics.
  Glama scores and some lists use these. Suggested (not done):

  ```bash
  gh repo edit WarreAndVavasour/WorkspaceAlberta \
    --description "MCP server for Canadian public procurement: CanadaBuys and Alberta Purchasing Connection tenders, ranked for your business." \
    --homepage "https://warreandvavasour.com/workspacealberta?utm_source=github&utm_medium=directory&utm_campaign=workspacealberta" \
    --add-topic mcp --add-topic mcp-server --add-topic procurement --add-topic canadabuys \
    --add-topic tenders --add-topic alberta --add-topic canada --add-topic construction
  ```

  Choosing a license is Christian's call.

## 5. mcp.so

- **Status:** Not verified as listed.
- **Form at `https://mcp.so/submit`:** "Repository URL" (required) and "Name".
  The page also shows a "Pay and submit automatically" button; do not use it
  (paid). The free path may need sign-in; not verified.
- **Values:** Repository URL `https://github.com/WarreAndVavasour/WorkspaceAlberta`,
  Name `workspaceAlberta`. If an edit page offers more fields, use Shared listing
  values with website `utm_source=mcpso`.

## 6. awesome-mcp-servers (punkpeye)

- **Status:** Not listed (no CanadaBuys, Alberta or workspaceAlberta entry).
- **Rules (CONTRIBUTING.md):** one server per line; link name to repo; brief
  description; alphabetical within the category; public GitHub repo required
  (remote-only servers go to a separate list, but this repo is public and
  contains the server source, so it qualifies).
- **Category:** Search & Data Extraction. That is where the existing public
  procurement servers sit (`atlasprzetargow/mcp-server` for Polish tenders,
  `qune-tech/ocds-mcp` for German OCDS).
- **Line** (insert alphabetically, after entries starting `W` that sort before
  `WarreAndVavasour`):

  ```markdown
  - [WarreAndVavasour/WorkspaceAlberta](https://github.com/WarreAndVavasour/WorkspaceAlberta) - Search Canadian public tenders from CanadaBuys and Alberta Purchasing Connection: deadlines, source postings, Buy Canadian flags and fit ranking for any business. Hosted at https://elbowsupknivesout.warreandvavasour.com/mcp.
  ```

  The list's legend uses glyph markers after the name (official, Python, cloud
  service). Our house rule is no emoji in anything we write, so the line has
  none. If the maintainers ask for them, the applicable markers are: official
  implementation, Python, cloud service. Other entries also carry a Glama score
  badge; add it once the Glama entry is under WarreAndVavasour.
- **PR title:** `Add WarreAndVavasour/WorkspaceAlberta (Canadian public procurement)`

## 7. Cursor

- **Status:** No public submission process found for an MCP directory run by
  Cursor. Cursor's docs point publishers to Plugins (which can bundle MCP
  servers) on the Cursor Marketplace, but do not explain submission. Not
  verified. `cursor.directory` (community site) returned HTTP 429 to our fetch,
  so its form is unverified.
- **What we can ship today:** an "Add to Cursor" install link (format from
  Cursor's install-links docs; config is base64 of `{"url":"https://elbowsupknivesout.warreandvavasour.com/mcp"}`):

  ```text
  cursor://anysphere.cursor-deeplink/mcp/install?name=workspaceAlberta&config=eyJ1cmwiOiJodHRwczovL2VsYm93c3Vwa25pdmVzb3V0LndhcnJlYW5kdmF2YXNvdXIuY29tL21jcCJ9
  ```

- **cursor.directory steps (unverified):** sign in at `https://cursor.directory`
  with GitHub, open its MCP submit page, use Shared listing values with website
  `utm_source=cursor-directory`.

## 8. GitHub MCP Registry / VS Code MCP gallery

- **Status:** Not listed.
- **How it gets populated:** GitHub's MCP Registry (`https://github.com/mcp`),
  which backs the VS Code MCP server gallery, draws on the official MCP
  Registry. Publishing step 1 makes workspaceAlberta eligible. Third-party
  guides say GitHub curates which servers appear and that you can email
  `partnerships@github.com` to request inclusion. That is unverified against an
  official GitHub page; sending it is Christian's call.
- **VS Code install (works today):** `.vscode/mcp.json`:

  ```json
  {
    "servers": {
      "workspacealberta": {
        "type": "http",
        "url": "https://elbowsupknivesout.warreandvavasour.com/mcp"
      }
    }
  }
  ```

## UTM sources

| Directory | `utm_source` |
|---|---|
| Official MCP Registry | `mcp-registry` (already in `server.json` `websiteUrl`) |
| PulseMCP | `pulsemcp` |
| Smithery | `smithery` |
| Glama | `glama` |
| mcp.so | `mcpso` |
| awesome-mcp-servers | none (the list links to the repo, not the website) |
| Cursor directory | `cursor-directory` |
| GitHub / VS Code | `github-mcp` |

All use `utm_medium=directory&utm_campaign=workspacealberta`.
