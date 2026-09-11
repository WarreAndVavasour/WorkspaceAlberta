# Launch review — 4 September 2026

## Prepared locally

- Personal story augmented in the WorkspaceAlberta, workspaceAlbertaSetup and workspacealberta-harness root READMEs. Existing historical image references in the procurement and harness READMEs are preserved. The harness Chinese README carries the new product chapter alongside its existing upstream material.
- New `/terminal` page in `warre-vavasour`, linked from every main navigation and the home and procurement pages. Includes search/social metadata, a CAD service offer in JSON-LD, a sitemap entry, accessible FAQs, agent-discovery copy and a functional connection-copy button.
- $4,800 CAD monthly terminal; locally deployed Pi projects; support over Tailscale; the personal family-doctor practice serving a small flock of approximately 20 devices.
- Separate one-company offer: 60 days to find, fix and deliver, or both sides walk away. Proposed 25% share of attributable new revenue actually earned, never savings. Revenue attribution and the collection period are agreed before starting.
- Shared MCP initialization instructions, `get_server_guide`, tool side-effect annotations, discovery handoff fields and explicit MCP error flags for hosted denials and core errors. Cohere route guidance and a research protocol distinguish operational traces from future RL datasets.
- [Announcement draft](launch-announcement.md) and [commercial draft](terminal-offer.md).

## Verification

- 63 Python tests passed across MCP startup, HTTP, agent contracts, billing gates, Cohere/Alberta behavior, production hardening, telemetry and bid-room processing. Tests ran with `CANADABUYS_LOAD_ENV_FILE=0` and `POSTHOG_API_KEY` empty to isolate local credentials and telemetry. A combined run without that isolation exposed cross-test queued telemetry; the isolated run and standalone telemetry tests pass.
- Website TypeScript lint, production build and route smoke checks passed. `/terminal` is included in the multi-page build and smoke loop.
- Browser checks cover desktop and a 390-pixel mobile viewport, layout overflow, the copy button and rendered content. Static checks cover the heading, anchor targets, local image paths, offer JSON-LD, sitemap and preserved historical image references.
- The existing public MCP health endpoint returned HTTP 200 and tool discovery returned 25 tools using an explicit diagnostic User-Agent. The new guide is local and not yet deployed.

## Remaining limits

- No public posting, remote Git push, deployment, customer-device change or billing change has been made in this work.
- No live Cohere inference, E2B paid run, reinforcement-learning job or customer-data training export was run.
- Harness `pnpm run doc-sync` reports 20 passing and 8 failing gates: existing catalog, JSDoc, Markdown wrapping/linking, translation pairing and package-README issues. The pre-edit English product README already differed from the bilingual consistency record and the Chinese upstream README. That record has not been falsely re-certified. These inherited issues need a separate documentation maintenance pass before treating the whole harness documentation gate as green.
- GBrain source sync ran, with database/fact-absorption warnings. A no-embedding import of the announcement reported success, but keyword verification did not retrieve it in the active source. Index freshness is not verified.
- Installation scope, acceptance, new-revenue attribution, collection period, payment, tax treatment and equipment return/continuation must be recorded in the selected company's agreement before the challenge starts.

## Publication sequence after approval

Publish only the reviewed changes, keeping unrelated local work out of commits. Push the website changes through its existing DigitalOcean deployment, verify `/terminal`, metadata and sitemap through the Cloudflare domain, and deploy the MCP additions through its existing service process. Verify the public MCP initializes with the operating instructions and exposes `get_server_guide` before presenting that tool as available. Publish the coordinated README chapters and announcement against that working release. Customer installation and billing remain separately scoped.
