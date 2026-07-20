# WorkspaceAlberta Product Deck — Build Brief (for the executing agent)

Build a 13-slide 16:9 PPTX via the kimi-slides pptd workflow. Read these skill references first:
- `C:\Users\chris\AppData\Roaming\kimi-desktop\daimon-share\daimon\skills\kimi-slides\reference\pptd.md` (format; first 1000 lines cover all element types used here)
- `C:\Users\chris\AppData\Roaming\kimi-desktop\daimon-share\daimon\skills\kimi-slides\reference\cli.md` (check / screenshot / package)

## Output locations (hard constraints — everything inside C:\Users\chris\WorkspaceAlberta)

- pptd project dir: `C:\Users\chris\WorkspaceAlberta\output\workspacealberta-deck\` containing `workspacealberta-deck.pptd`, `pages/`, `media/`
- Copy needed images into `media/` from:
  - `C:\Users\chris\WorkspaceAlberta\docs\assets\women-workers-small-arms.jpg` (cover)
  - `C:\Users\chris\WorkspaceAlberta\docs\assets\sophie-okowinski-bren-gun.jpg` (problem slide)
  - `C:\Users\chris\WorkspaceAlberta\docs\assets\small-arms-machinist-laughing.jpg` (close, optional)
  - `C:\Users\chris\WorkspaceAlberta\assets\terminal\hero-render.png` (sovereignty slide)
- Final deliverable: `kimi-slides package` → `C:\Users\chris\WorkspaceAlberta\output\WorkspaceAlberta-Product-Deck.pptx`

## Design system — DUAL BRAND (this is the concept, do not flatten it)

Warre & Vavasour (the lab) frames the story in DARK editorial slides; WorkspaceAlberta (the product) works in LIGHT industrial slides. The alternation is the narrative: conviction in the dark room, work in daylight.

Dark slides: 1, 2, 3, 8, 11, 12. Light slides: 4, 5, 6, 7, 9, 10, 13.

### Dark palette (W&V, from warreandvavasour.com CSS)
- bg `#0a0807`, panel `#100c09`
- ink `#f3ede1`, ink-66 `#f3ede1a8`, ink-40 `#f3ede166`, ink-16 `#f3ede129`
- gold `#d9a441`, gold-2 `#e8c277`, ember `#c2542a`
- hairlines: `#f3ede11f` and `#f3ede138`

### Light palette (WorkspaceAlberta, from repo brand spec)
- paper `#f7f5ef`, white `#ffffff`, aluminum `#d6d3ca`, concrete `#b9b7ae`
- ink `#111111`, muted `#5f625f`
- copper `#b87333`, sky `#79a9d8`
- hairline `#11111124`

### Typography (skill font list — Fraunces/Inter Tight/JetBrains Mono are NOT available)
- Display headlines: **Oranienbaum** (serif stand-in for Fraunces) — 40–68px, never bold, tight line height 1.05–1.15
- Body / labels: **Liter** (neo-grotesque stand-in for Inter Tight) — 13–18px body
- "Technical mono" effect: Liter, uppercase, letterSpacing 2–3, 10–11px, used for corner labels, kickers, and data captions
- Corner labels on every slide: top-left section kicker, top-right `W&V · WORKSPACEALBERTA` — 10px letterspaced, 40% ink

### Signature devices
- Thin gold (dark) / copper (light) horizontal rules, 2px, short (80–160px), used under kickers
- Big editorial numerals for stats (Oranienbaum, 56–72px)
- Historical photos (Library and Archives Canada WWII industrial) with heavy dark overlay (`#0a0807` rect at ~72–80% opacity over image) — duotone feel; never full-strength color photos on dark slides
- "Artifact cards": real tool output quoted verbatim in bordered cards — authenticity is the brand
- Generous whitespace; 64px side margins; no gradients except subtle dark overlay gradients on photos; no stock-photo gloss

## Slide-by-slide copy (use verbatim unless layout forces trims)

Page size [960, 540]. Kicker label positions: [64,36,400,16]; page label top-right [660,36,236,16] right-aligned.

### S1 — Cover (dark)
- Background: `media/women-workers-small-arms.jpg` full-bleed cover + overlay rect `#0a0807` opacity 0.80 + subtle bottom gradient
- Kicker top-left: `WARRE & VAVASOUR · AN AI LABORATORY` (gold, letterspaced)
- Top-right: `BOW VALLEY, ALBERTA · 2026`
- Display ~64px, ink, around y 200: `Welcome to Work, Alberta.`
- Sub 16px ink-66, max width ~560: `WorkspaceAlberta — live government demand, wired directly to the people who can do the work.`
- Bottom strip above 40px from bottom: 2px gold rule (120px) + label: `PRODUCT BRIEF · THE FIRST OFFERING IS OPEN AND FREE`
- Small credit 9px ink-40 bottom-right: `Canadian industrial war production · Library and Archives Canada`

### S2 — The problem (dark)
- Kicker: `01 · THE LAST MILE`
- Headline 44px: `AI promised 5X productivity.`
- Second line 44px, ink-40 or ember accent on key words: `Most small businesses got a chatbot that writes mediocre marketing copy.`
- Body 15px ink-66, ~480px wide: `The model is not the bottleneck. The connection is. Government tender databases are the perfect example: the work is public, the demand is real, but the discovery process is still awkward enough that good companies miss good opportunities.`
- Right side: `sophie-okowinski-bren-gun.jpg` in a bordered panel (~300×340) with dark overlay 0.35, caption 9px: `Sophie O'Kowinski, John Inglis Co., 1943 · Library and Archives Canada`

### S3 — The ethos (dark)
- Kicker: `02 · THE SENTENCE THAT STARTS EVERYTHING`
- Lead-in serif italic-ish 22px gold-2: `Wouldn't it be great if…`
- Four stacked lines, Oranienbaum 24–26px ink, each preceded by an em-dash, with hairline separators:
  1. `a fabricator saw the right tender before the deadline was already too close`
  2. `a contractor could ask one question across federal and Alberta postings`
  3. `a shop owner got a daily bid brief without learning another portal`
  4. `a good bid/no-bid decision took minutes instead of a lost afternoon`
- Footer 13px ink-40: `This is not a prompt library. It is the bottleneck, stated plainly.`

### S4 — What it is (light — first porcelain slide; the transition is intentional)
- Kicker: `03 · THE PRODUCT` (copper)
- Headline 40px ink: `The custom MCP server is the product.`
- Body 14px muted, ~520px wide: `A deployed, working endpoint that knows the live public procurement pipeline — CanadaBuys and Alberta Purchasing Connection — and serves it back through any AI assistant, ranked by what you do, where you work, and what deadlines matter. No new portal to babysit.`
- Diagram strip (shapes, lower half): three source chips `[CANADABUYS · FEDERAL]` `[ALBERTA PURCHASING CONNECTION]` → arrow → center card `WORKSPACEALBERTA MCP · 21 TOOLS` (white card, copper border) → arrow → chip `[ANY AI ASSISTANT · MCP / REST]`
- Caption 9px muted: `Pure Python procurement core. The model layer is added only where judgment helps. Same core exposed as REST/OpenAPI.`

### S5 — Hero moment (light)
- Kicker: `04 · LIVE TEST · JULY 18, 2026` (copper)
- Headline 36px: `One sentence about your shop. A ranked tender list in 30 seconds.`
- Left card (~360px wide, white, hairline border): label `THE INPUT — ONE SENTENCE`; quote 15px ink: "Custom metal fabrication shop: structural steel, stairs, railings, platforms, CWB-certified welding. 12 employees, Edmonton." — attribution 10px muted: `Ironline Fabrication Ltd. · test persona`
- Right card (~460px wide): label `THE OUTPUT — RANKED MATCH`; big score badge: Oranienbaum 56px copper `91` + `MATCH SCORE` label; then: `Alberta Transportation & Economic Corridors — ITB TND0012201`; `Structural steel girder bridge · Hwy 2 interchange, Morinville AB`; `Closes 2026-07-30 · 11 days remaining`; why-it-matches 10px muted: `matches: steel · structural steel · fabrication · supply · delivers to Alberta`
- Footer 9px muted: `REAL DATA · ALBERTA PURCHASING CONNECTION · REF AB-2026-04073 · RETRIEVED LIVE VIA MCP`

### S6 — The 7:00 AM brief (light)
- Kicker: `05 · THE HABIT` (copper)
- Headline 40px: `The market, before coffee.`
- Two big stats side by side: Oranienbaum 64px `850` label `FEDERAL OPEN NOTICES · CANADABUYS` ; `1,523` label `ALBERTA OPEN OPPORTUNITIES · APC` ; caption 9px: `LIVE COUNTS · JULY 18, 2026`
- Three column chips below: `BEST FITS` / `CLOSING SOON` / `SUGGESTED ACTION` with 11px muted descriptors (ranked against your profile / closing-date countdowns / the next move, stated plainly)
- Bottom line 14px, copper accent on "Free. Permanently.": `The daily bid brief is free. Permanently. The habit stays free while it forms — and after.`

### S7 — Depth (light)
- Kicker: `06 · THE DETAILS THAT DECIDE` (copper)
- Headline 36px: `The three numbers that matter, out of the 140-page RFP.`
- Artifact card from real tender AB-2026-04073, two-column fact list (label 10px letterspaced muted / value 13px ink):
  - `MANDATORY` / `Certificate of Recognition (CoR)`
  - `BID BOND` / `Digital format, required with every tender`
  - `SUBMISSION` / `Email only — hard copy refused`
  - `PRE-TENDER MEETING` / `June 10, 2026 · MS Teams`
  - `CONTACT` / `Named procurement officer, gov.ab.ca`
  - `SCALE` / `279,400 m³ excavation · 57,000 t asphalt · HP 310×110 steel piling`
- Footer 9px: `GET_OPPORTUNITY_DETAILS · VERBATIM TOOL OUTPUT · REF AB-2026-04073`

### S8 — The business model (dark)
- Kicker: `07 · FREE BRIEF, PAID BID WORK` (gold)
- Headline 40px: `Free to look. $85/month to bid.`
- Two columns with hairline borders: left header `FREE FOREVER` — `Search both governments in one question` / `Daily bid brief` / `Full tender details` / `Closing-soon deadlines`; right header `PRO · $85 CAD/MONTH` (gold) — `Bid rooms: sandboxed E2B analysis of full tender packages` / `Cohere Command A+ review: risks, requirements, fit score` / `Watchlist with closing-date countdowns` / `Bid/no-bid scorecards on demand`
- Artifact strip bottom: bordered dark panel quoting the real paywall verbatim, 12px ink-66: "WorkspaceAlberta Pro required. A WorkspaceAlberta Pro API key is required for this tool." + caption 9px gold: `THE ACTUAL PAYWALL, VERBATIM · THE METER STARTS AT THE MOMENT OF INTENT`

### S9 — Proof (light)
- Kicker: `08 · TESTED, NOT PROMISED` (copper)
- Headline 36px: `We ran the user tests before we made this deck.`
- Six stat chips in 2 rows of 3 (big Oranienbaum numeral + 10px label): `5.4 s` fresh clone · `49 s` dependency install, clean on Windows · `7/7` smoke tests passing · `21` MCP tools live · `~2 s` first live search · `30 s` from one sentence to ranked matches
- Honest block, 12px muted: `What broke: the README has no setup path, naming is inconsistent, and the AI review tool dead-ends on Alberta references. All logged with fixes ranked in docs/user-tests/. We show the seams.`

### S10 — Market (light)
- Kicker: `09 · WHO THIS IS FOR` (copper)
- Headline 40px: `2,500 companies. $37 billion. One search box away.`
- Table (3 rows + header, hairline borders, no fills except header `#111111` text on aluminum): columns SECTOR / COMPANIES / IMPACT / JOBS — rows: `Forestry & wood products` `676+ businesses, 40 major mills` `$14B` `41,400`; `Fabricated metal products` `1,871 establishments` `$23.4B sector` `16,600`; `Primary & machinery mfg.` `200+ facilities` `included above` `12,000+`
- Footer chips 11px muted: `$4B forest exports` · `70 communities depend on these industries` · `$988M tax revenue` · caption 9px: `STATISTICS CANADA · INNOVATION CANADA · ALBERTA FOREST PRODUCTS ASSOCIATION`

### S11 — Sovereign stack (dark)
- Kicker: `10 · THE SOVEREIGN PATH` (gold)
- Headline 38px: `Canadian AI security is Canadian national security.`
- Left stack list (label/value pairs, 11px labels gold letterspaced, 14px values ink): `DEMAND` CanadaBuys + Alberta APC · `MODEL` Cohere Command A+ (open, W4A4 on Hugging Face) · `TOOLS` this MCP server, open and free · `COMPUTE` managed terminals now; Canadian-built Linux devices on the long path
- Right: `hero-render.png` (the WorkspaceAlberta terminal) panel ~340×360, caption 9px ink-40: `THE WORKSPACEALBERTA TERMINAL · ASSEMBLED NOW, CANADIAN-BUILT ON THE LONG PATH`
- Sub 13px ink-66: `The point is not nationalism as decoration. The point is operational independence.`

### S12 — Close (dark)
- Optional faint background: `small-arms-machinist-laughing.jpg` with overlay 0.88
- Headline 56px centered-ish left: `Canada is going to work.`
- Sub 15px ink-66: `More contracts won. More jobs kept. More skill developed. More value staying here at home.`
- Two CTA blocks: `READ THE BRIEF TOMORROW — FREE` `github.com/HarleyCoops/WorkspaceAlberta` ; `READY TO BID — $85 CAD/MONTH` `buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a` (gold rule above each)
- Bottom: `WARRE & VAVASOUR · AN AI LABORATORY · BOW VALLEY, ALBERTA` left, right: `BUILT FOR TRADES, NOT TECH`

### S13 — Appendix: the brand answer (light)
- Kicker: `APPENDIX · ONE FAMILY, TWO REGISTERS` (copper)
- Headline 32px: `Should the product have a separate brand? No — a register, not a divorce.`
- Left column: `WARRE & VAVASOUR — THE LAB` swatch chips `#0a0807` `#d9a441` `#c2542a` `#f3ede1`; note: dark, editorial, conviction. Fraunces → Oranienbaum in this deck.
- Right column: `WORKSPACEALBERTA — THE PRODUCT` swatches `#f7f5ef` `#b87333` `#79a9d8` `#111111`; note: porcelain, industrial, daylight. The product the lab stands behind.
- Rule line: `Dark slides make the argument. Light slides do the work.`
- Imagery note 10px muted: `Library and Archives Canada industrial photography, duotone treatment. No stock gloss, no fake stats, no fake testimonials.`

## Build process
1. Read the two reference docs, copy media, author `.pptd` + 13 `.page` files.
2. `kimi-slides check` the project; fix all errors and serious warnings (TextOverflow, TextOcclusion, BoundsOutside). TextUnderFill on big display text is acceptable.
3. `kimi-slides screenshot` all pages; stitch a grid overview (Python PIL is available) AND inspect each page at full size. Judge like an art director: alignment, spacing, hierarchy, overflow, contrast. Fix and re-screenshot at least 2 full rounds — this deck must look genuinely premium.
4. `kimi-slides package` to the final pptx path; verify the file exists and is non-trivial in size.
5. Do not modify any repo files outside `output/`. Do not leave servers running.

Return: final pptx path, slide count, what you fixed across screenshot rounds, and any remaining visual compromises.
