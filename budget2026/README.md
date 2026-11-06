# Budget 2026 Explorer

`budget2026.warreandvavasour.com` — Warre & Vavasour's independent explorer of Canada's federal Budget 2026, *Masters of our destiny* (tabled November 5, 2026). A traffic page for people searching #budget2026 that also shows our work: federal money becomes programs, programs become projects, projects become RFPs, and we help businesses plan, tool up and deliver.

## What it is

- **Map** (home page): a JSON Crack-style tree, budget → chapter → section → measure, adapted from the workspaceAlberta requirements board (`procurement_core/templates/requirements-board.html`). Search, lenses, money-type filters, list view, deep links (`/#m=<slug>`, `/#lens=trades`).
- **181 measure pages** (`/measures/<slug>/`): cost line by year with “Less:” adjustments, proposal quotes with page cites, key facts, amounts named in the text, W&V commentary where we have something to say.
- **13 lens pages** (`/topics/<lens>/`): households, housing, businesses, trades, investment, training, defence, energy, AI & digital, Indigenous communities, infrastructure, public work (W&V lens), health. Totals stay separated by money type.
- **Chapters**, **fiscal outlook** (deficit, debt, revenues, expenses, capital vs operating, loans), **tax changes** (all 49 annex measures), **methodology**.
- **Agent-readable**: every page has a JSON twin (`<link rel="alternate" type="application/json">`), plus `/data/budget.json`, `/data/explorer.json`, `/llms.txt`, `/sitemap.xml`, JSON-LD.
- **Agent broadcast** (`scripts/agent_files.py`): `/agents.md` (endpoints, record format, rules, Claude Agent SDK examples in Python and TypeScript), `/skill.md` (drop-in Claude Agent Skill, save as `.claude/skills/budget2026/SKILL.md`) and `/.well-known/agent-card.json` (same shape as warreandvavasour.com's card). All point agents to the workspaceAlberta MCP for live tenders.
- **Analytics** (`assets/site.js`): PostHog, same project as warreandvavasour.com, every event tagged `product=budget2026` with `page_type` and `slug`. No cookies (sessionStorage), no person profiles, no autocapture, no session recording; honours Do Not Track / GPC; runs only on `*.warreandvavasour.com`. Events: `$pageview`, `$pageleave`, `link_clicked` and `button_clicked` (every link and button: `label`, `section`, `element`, and for links `link_type`, `destination` without its query string, `destination_host`; form fields are never read; `data-track-skip` opts an element out), `budget_outbound_click` (destination: workspacealberta, claude_connector, training, ai_terminal, million_dollar_problem, pacific_link, wv_home, official_budget), `budget_data_opened`, `budget_search` (query, results), `budget_lens_selected`, `budget_measure_opened`, `budget_chapter_opened`, `budget_view_changed`, `budget_filter_changed`, `budget_map_fullscreen`.

## Money types (never added together)

| Type | Meaning |
|---|---|
| Program spending | Yearly accrual impact on the budgetary balance |
| Tax measure | Forgone or raised revenue through the tax system |
| Savings or revenue | Improves the balance |
| No cost line | A heading with no line of its own in the chapter cost table |
| Loans, equity or financing (flag) | Lending or investment involved; face value is not budgetary cost |

## Build

```
python scripts/build_all.py              # -> out/
python scripts/build_all.py --preview    # -> out-preview/ (relative links)
```

Standard library only; no model or API key. `data/source.json` (the full page text) is not committed because this repo is public; create it from the budget PDF with `python scripts/index_pdf.py budget-2026.pdf` (needs PyMuPDF) before building. `scripts/verify.py` runs on every build and fails it if any transcribed fiscal value, section subtotal, tax value or key-fact number does not match its cited page.

| File | Role |
|---|---|
| `scripts/index_pdf.py` | PDF → `data/source.json` (page text + bookmarks). Needs PyMuPDF. |
| `scripts/parse_tables.py` | Six chapter cost tables → `data/tables.json` |
| `scripts/extract.py` | Measures, proposal quotes, money types, lenses → `data/measures.json` |
| `scripts/taxonomy.py` | Lenses, official URLs, **W&V editorial overrides and key facts** (edit here) |
| `scripts/annex.py` | Tax annex Table 1 → `data/tax.json` |
| `scripts/fiscal_data.py` | Hand-transcribed fiscal tables (checked by verify.py) |
| `scripts/build_site.py` | Static site generator |
| `scripts/agent_files.py` | agents.md, skill.md, agent card |
| `assets/` | CSS, map JS, tooltip JS, social image |

`dist/` is the earlier Codex draft (full page text and the PDF). It is not deployed; delete it when you are happy with `out/`.

## Source and rights

Built from the 532-page PDF (SHA-256 `26e60cd8…6e19`). The PDF says “All rights reserved”, so the site does **not** republish the full text or the PDF: it quotes short excerpts for review and commentary and links every citation to the official chapter on budget.canada.ca. Not a Government of Canada website.

## Deploy (Cloudflare Workers static assets)

```
python scripts/build_all.py
npx wrangler@4 deploy
```

`wrangler.jsonc` deploys `out/` as the assets-only Worker `warre-vavasour-budget2026` with the custom domain `budget2026.warreandvavasour.com` (Cloudflare creates the DNS record and certificate). `out/_headers` sets security headers and CORS on `/data/*`, `/agents.md`, `/skill.md` and `/.well-known/*`. Uses the wrangler OAuth login on Christian's PC.

## Next

- When the official PDF URL is confirmed, add `#page=` deep links next to the chapter links.
