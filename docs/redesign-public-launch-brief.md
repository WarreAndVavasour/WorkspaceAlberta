# WorkspaceAlberta Redesign + Public Launch Brief

Status: first research/design synthesis, 2026-06-14.

## 1. Research scan: small/niche AI lab design patterns

The strongest AI-lab/startup sites are not winning because they look generically futuristic. They win because the site makes one category legible fast and then proves the company can actually ship.

Examples and takeaways:

- Anthropic / Claude pattern: warm authority, sparse editorial copy, restraint. Useful lesson: trust can come from quietness, not neon.
- Cohere pattern: enterprise AI infrastructure, white canvas, strong rounded cards, restrained color, product/architecture credibility. Useful lesson: Cohere should read as a trusted route/tool inside WorkspaceAlberta, not as the whole brand.
- Linear / Cursor / VoltAgent pattern: dark command-deck surfaces, exact type, code/workflow artifacts as visual proof. Useful lesson: the work layer can be shown as a cockpit/operating surface, not another marketing page.
- Wispr Flow pattern: calm editorial background, one motion/product explanation, simple visual system. Useful lesson: explain one human workflow rather than every technical capability.
- Perplexity pattern: product is the interface. Useful lesson: if the promise is “ask across your work,” the site should show actual queries, artifacts, and outputs.
- Runway / Midjourney pattern: output as proof. Useful lesson: screenshots, bid-room artifacts, filled documents, and generated work products should replace abstract AI illustrations.
- Listen Labs pattern: niche AI product framed around a clear business process, with example reports. Useful lesson: show the recurring artifact the customer gets back.

General design rules for WorkspaceAlberta:

1. Lead with the category, not the stack.
2. Show real work artifacts, not abstract AI graphics.
3. Use hardware presence to make the promise tangible.
4. Make the user feel continuity: this is an operator that stays with the business.
5. Treat MCP as the connection layer behind the work, not as the headline.
6. Keep Cohere visible as the Canadian reasoning route/single tool for document/tender analysis, but do not let it dominate the product story.

## 2. Reframe: WorkspaceAlberta is a new work layer

Old frame:

- Canadian procurement intelligence
- CanadaBuys/APC search
- MCP server
- Cohere analysis
- daily bid brief

New frame:

- WorkspaceAlberta is a managed AI operator layer for medium-scale industrial businesses.
- It lives in a dedicated on-premise/custom device installed in the owner’s office.
- It keeps the plates spinning: connectors, APIs, credentials, settings, MCPs, documents, workflows, and agents.
- The point is not chat. The point is that the user can ask for something useful and the system helps actually build it.
- Procurement is the first working trade-specific tool, not the whole company.

Category sentence:

> WorkspaceAlberta installs and operates the AI work layer for Canadian industrial businesses: a dedicated terminal, a managed Hermes/Codex agent stack, and trade-specific tools that turn “wouldn’t it be great if…” into working systems.

Short homepage line:

> This is not AI as a tab. This is AI as a place to work.

Operational promise:

> Bring us the bottleneck. The terminal keeps the context, the connectors, the documents, and the agents live long enough to build the tool the business actually needs.

## 3. Product architecture story

The public site should explain the system as four layers:

1. The room layer
   - A visible terminal installed where the owner works.
   - Raspberry Pi control node and clean dual-display workstation as the physical trust anchor.
   - On-premise/local posture for presence, continuity, and privacy.

2. The operator layer
   - Hermes Agent as the always-available operating surface.
   - Codex 5.5-class coding/building loop for turning ideas into working tools.
   - Skills, memory, session search, cron, subagents, browser/devtools, files, terminal, web, and MCP-loaded tools.

3. The connector layer
   - MCP servers and APIs as the wiring.
   - CanadaBuys/APC as the first public-demand connector.
   - Cohere Command A+ as one reasoning tool for Canadian document/tender analysis.
   - E2B as isolated sandbox compute for risky/heavy document packages.

4. The trade-tool layer
   - Procurement bid room.
   - Quote/invoice triage.
   - Inventory-to-RFP fit review.
   - Compliance package builder.
   - Custom workflow tools built per company.

## 4. Latest Hermes tools to feature in the design

Based on the current Hermes docs and local toolset, the design should show Hermes as a work operating system with these capabilities:

- MCP support: local stdio and remote HTTP MCP servers; dynamic tool discovery; selected tool filtering; catalog installs via `hermes mcp`.
- Skills: reusable procedures that make the operator improve over time; every skill can become a slash-command-like capability.
- Memory + session search: continuity across work, not one-off chat.
- Delegation/subagents: parallel workstreams for research, coding, cleanup, and verification.
- Cron jobs: daily bid brief, scheduled checks, connector health, deadline watch.
- Terminal/file/web/browser/vision tools: the agent can inspect, edit, run, verify, and report real work.
- Official Chrome DevTools MCP path: useful for real-browser design QA and web-app operation without relying on the WSL/Chromium stack.
- Image generation/vision/design skills: useful for product mockups, terminal render direction, and visual QA.

How to say it publicly:

> WorkspaceAlberta runs a managed Hermes agent installation with selected MCP tools, skills, memory, scheduled jobs, and build agents. The owner sees one workspace. Underneath, the system keeps the connectors and operators alive.

Do not lead with tool names in the hero. Use them in the “what lives inside the terminal” section.

## 5. Visual framing direction

Working title:

> The Work Layer

Visual metaphor:

- Not “AI cloud.”
- Not “dashboard.”
- Not “chatbot.”
- A control room / bid room / shop office operating layer.
- The physical terminal is the visible object; the work layer is shown as stacked plates, live connectors, and finished artifacts.

Core visual system:

- Base: porcelain / warm white / brushed aluminum / concrete gray.
- Accent: copper from the Pi/cooling and restrained Alberta sky blue.
- Secondary mode: dark command-deck panels for the operator layer.
- Type: precise modern sans; small mono labels only for tool names and live system states.
- Images: real Canadian industrial production photos, terminal renders/photos, artifact screenshots.
- Motion: mechanical line draws, plate spin/stack metaphor, connectors lighting up only when relevant.

Avoid:

- Generic “AI orb” gradients.
- Museum-only heritage styling as the main experience.
- Huge feature-card grids.
- Treating Cohere as the product.
- Treating Raspberry Pi like a hobby board.
- SaaS claims like “unlock productivity.”

## 6. Homepage structure proposal

1. Hero: `Welcome to Work, Alberta.`
   - Full-bleed or large hero of the terminal.
   - Subline: `A managed AI work layer for the owners building Canada’s industrial economy.`
   - CTA: `Build the workspace` / `See what it builds`.

2. Category definition: `The new layer of work`
   - Explain that medium-scale businesses need a trusted AI operator, not another subscription.
   - Show: owner, terminal, connectors, artifacts.

3. The operating promise: `Wouldn’t it be great if...`
   - Turn the phrase into a build pipeline:
     - sentence → context → connector → sandbox → artifact → recurring tool.

4. First working tool: `Public work, made actionable`
   - Procurement is the concrete proof.
   - CanadaBuys/APC, bid brief, bid/no-bid, E2B document package processing.
   - Cohere appears here as the Canadian document-reasoning tool.

5. What lives inside the terminal
   - Hermes Agent, Codex-class build loop, selected MCP servers, skills, memory, cron jobs, remote support, connector health.

6. On-premise/custom device
   - Explain the Raspberry Pi control-node installation, local presence, managed support, clean hardware.

7. Proof artifacts
   - Screenshots/examples: bid-room artifact, filled form, connector health, daily brief, document extraction.

8. Canadian industrial continuity
   - WWII production images as serious visual memory: Canada has done industrial mobilization before; now the bottleneck is coordination and work wiring.

9. Installation/subscription model
   - Installed, configured, supported, improved.

10. Close
   - `This is AI as a place to work.`

## 7. WW2 / industrial imagery added

New downloaded Library and Archives Canada / BiblioArchives images:

- `docs/assets/john-inglis-weld-magazine-clips.jpg`
  - Workers welding Bren gun magazine clips at John Inglis Co., Toronto, April 1944.
- `docs/assets/small-arms-machinist-laughing.jpg`
  - Woman machinist at Small Arms Limited, Long Branch, May 26, 1942.
- `docs/assets/john-inglis-assembling-bren-blank.jpg`
  - Woman munitions worker assembling a Bren gun blank at John Inglis Co., May 10, 1941.

Existing images already in the repo:

- `docs/assets/women-workers-small-arms.jpg`
- `docs/assets/sophie-okowinski-bren-gun.jpg`
- `docs/assets/helene-lalonde-textile.jpg`
- `docs/assets/ready-for-action-shells.jpg`

Usage direction:

- Use these as section anchors and archival proof, not as nostalgic wallpaper.
- Pair each photo with a modern work-layer artifact: war production coordination then; agentic work coordination now.
- Keep source/credit visible in an image index or credits drawer.

## 8. Public repo readiness findings

Current remote state:

- `HarleyCoops/WorkspaceAlberta` is currently PRIVATE.
- Local branch: `codex/bid-room-diagram-assets` tracking `origin/codex/bid-room-diagram-assets`.

Main blockers before making public:

1. Tracked `output/` directory is large/noisy and contains generated CanadaBuys CSV/JSON/project outputs plus devcontainer material.
   - 58 tracked files under `output/`.
   - Recommendation: remove from git or move representative sanitized examples to `docs/examples/`.

2. Tracked `xxxQuarantine/` exists.
   - 13 tracked files, including old template/demo workspace configs.
   - Recommendation: remove from public history or at least delete from current tree before public release.

3. `.claude/skills/gbrain/SKILL.md` is tracked.
   - Current repo guidance says not to reintroduce Claude-specific guidance, but this exists.
   - Recommendation: remove or migrate to `hermes/skills/` only if a public skill is intended.

4. `.cursor/mcp.json` points at the live Cloud Run endpoint.
   - This may be okay if the endpoint is intentionally public/unauthenticated; otherwise it needs auth/domain hardening first.

5. `env/.env.example` includes generic Hootsuite/Shopify/Stripe variables unrelated to the narrow public product.
   - Recommendation: either remove or rename as legacy; keep only WorkspaceAlberta/Hermes/CanadaBuys/Cohere/E2B examples.

6. Docs mention many future/legacy paths: Codespaces, output templates, Shopify/Hootsuite, multi-user GitHub-generated repos.
   - Recommendation: make the public repo narrow: one hosted MCP product, one local MCP server, one Hermes/Pi installer, one bid-room plan, one image/source manifest.

7. Secret scan of tracked files found no obvious literal secret values, only variable names/placeholders. Still run a stronger scan before public release.

Public-release cleanup sequence:

1. Create a release branch from the intended base branch.
2. Remove `output/` and `xxxQuarantine/` from tracked files.
3. Add `.gitignore` rules for generated outputs, local `.env`, raw tender packages, E2B scratch, and sandbox artifacts.
4. Simplify README so it matches the new frame: work layer → terminal → procurement tool → technical setup.
5. Keep `docs/imagery-sources.md` and credits current.
6. Run tests:
   - `python -m unittest tests.test_canadabuys_mcp_smoke`
   - `python -m pytest tests/test_procurement_http_app.py -q` if pytest deps are installed.
7. Run a public-safety scan:
   - `git grep -n -I -E '(sk-|ghp_|gho_|BEGIN .*PRIVATE|API_KEY=.*[A-Za-z0-9])'`
   - optionally `gitleaks detect --no-banner` if installed.
8. Only then use `gh repo edit HarleyCoops/WorkspaceAlberta --visibility public` after explicit final confirmation.

## 9. Immediate implementation recommendation

Do not polish the current `warreandvavasour.com` museum-style homepage. It is pointed at the wrong center of gravity.

Build a new WorkspaceAlberta-first product page/prototype that uses:

- a light industrial terminal/product-film design,
- dark operator panels for the Hermes/Codex/MCP system,
- real WWII Canadian industrial images as historical continuity,
- real bid-room/daily-brief artifacts as proof,
- Cohere as one named analysis tool,
- E2B as the isolated document-processing pipeline,
- Hermes as the managed work operating layer.

The current Warre & Vavasour site can later become the lab umbrella. WorkspaceAlberta needs its own page that makes the new category obvious in the first screen.
