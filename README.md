# WorkspaceAlberta

<p align="center">
  <img src="docs/assets/women-workers-small-arms.jpg" alt="Women workers at Small Arms Limited, 1942." width="49%">
  <img src="docs/assets/sophie-okowinski-bren-gun.jpg" alt="Sophie O'Kowinski reaming a Bren gun barrel at the John Inglis Company munitions plant, 1943." width="49%">
</p>

<p align="center"><em>Canadian industrial war production, via Library and Archives Canada.</em></p>

## Canadian AI Security Is Canadian National Security

Canada should not discover its own industrial demand through foreign dashboards, foreign workflows, and foreign defaults.

WorkspaceAlberta is a Canadian procurement intelligence workspace. It connects public tender data to the people who can actually do the work: fabricators, mills, contractors, shops, manufacturers, and the small teams that keep the real economy moving.

The direction is explicit:

- **Canadian demand signals:** CanadaBuys and Alberta Purchasing Connection in one search surface.
- **Canadian AI company:** Cohere as the first sovereign-model route.
- **Canadian open source model:** Command A+ `command-a-plus-05-2026`, with the W4A4 Hugging Face route available through `CohereLabs/command-a-plus-05-2026-w4a4`.
- **Canadian tools:** practical MCP wiring for the procurement sources Canadian firms already need to watch.
- **Canadian compute path:** designed so sensitive public-sector and industrial workflows can move toward Canadian infrastructure, including Canadian chips and data-centre capacity where those options are available.

The point is not nationalism as decoration. The point is operational independence.

If Canadian companies are going to bid Canadian work, understand Canadian supply chains, and protect Canadian industrial capacity, then the AI layer underneath that work matters.

---

## The Last Mile of Work

AI promised 5X productivity. Most small businesses got a chatbot that writes mediocre marketing copy.

The model is not the whole bottleneck. The connection is.

Wiring up the places where the work lives usually costs money, time, and technical patience a small business does not have. Government tender databases are a perfect example: the work is public, the demand is real, but the discovery process is still awkward enough that good companies miss good opportunities.

**WorkspaceAlberta solves the last mile** by giving an AI assistant the wiring it needs to search, compare, summarize, and brief public procurement opportunities from inside the workspace where the owner is already working.

---

## "Wouldn't It Be Great If..."

This is not a prompt library.

It is the sentence a business owner says when they can feel the friction in the operation but do not yet have the wiring to remove it.

"Wouldn't it be great if..." is not marketing copy. It is the bottleneck, stated plainly.

Wouldn't it be great if:

- a fabricator saw the right tender before the deadline was already too close
- a contractor could ask one question across federal and Alberta postings
- a shop owner got a daily bid brief without learning another portal
- a Canadian model could help triage Canadian public work using Canadian tools
- a good bid/no-bid decision took minutes instead of a lost afternoon

The job of this workspace is to turn that sentence into faster decisions, fewer missed opportunities, and more useful output from the people already doing the work.

---

## What This Actually Does

WorkspaceAlberta is an MCP-first workspace for Canadian procurement.

It now brings together:

- **CanadaBuys** for federal tender notices
- **Alberta Purchasing Connection** for Alberta public-sector opportunities
- **Cohere Command A+** for optional tender analysis and fit review
- **A daily bid brief** that summarizes the market, best-fit matches, and deadlines from both sources

The assistant can:

- search national and Alberta opportunities together
- inspect a posting by reference number
- list what is closing soon
- match opportunities against a saved business profile
- generate a free daily brief for the owner or estimator
- use Cohere Command A+ to review tender fit, risks, requirements, and next actions

This is meant to answer practical questions:

- What work is open right now?
- Which opportunities fit what we actually do?
- What closes soon?
- What should we read first?
- What should we ignore?

---

## The Custom Procurement MCP Server

The custom MCP server is the product.

It is a deployed working endpoint that knows the live public procurement pipeline exposed by **CanadaBuys** and **Alberta Purchasing Connection**. It can serve that pipeline back to users through an AI assistant based on what they do, where they work, what they can supply, and what deadlines matter.

The core tools are:

- `search_opportunities` for unified federal and Alberta search
- `get_opportunity_details` for a single posting by reference number
- `list_deadlines` for what is closing soon
- `find_matching_opportunities` for profile-based ranking
- `daily_bid_brief` for the daily owner/operator summary
- `analyze_contract_with_cohere` for optional Cohere Command A+ tender review
- `process_bid_room` for live E2B attachment extraction and Cohere tool-assisted bid review

MCP is the first-class interface because this is meant to be used by agents. The same procurement core also exposes REST/OpenAPI so other AI tools can hook into the same contract intelligence without needing native MCP support.

Underneath the endpoint is pure Python procurement logic. The data processing, filtering, matching, deadline ranking, and brief generation do not require an LLM. The model layer is added only where judgment helps: risk review, requirements explanation, and bid/no-bid reasoning.

E2B sandboxes are the isolated compute layer for heavier bid-room work: opening tender packages, parsing attachments, extracting compliance requirements, and returning structured bid artifacts without putting unknown user files inside the always-on MCP service. Cohere Command A+ runs inside the short-lived sandbox with read-only evidence tools over the extracted documents. The build plan lives in [`docs/e2b-bid-room-plan.md`](docs/e2b-bid-room-plan.md), and the business-owner operating diagram lives in [`docs/bid-room-operating-diagram.md`](docs/bid-room-operating-diagram.md).

---

## Free First

The daily bid brief should be free while the habit is forming.

A $12/month weekly update might make sense later, but charging too early would slow down the more important goal: getting Canadian businesses used to checking public demand every day with an assistant that understands their capabilities.

The sequence is:

1. Build trust.
2. Build the community.
3. Prove the brief saves time.
4. Price only when people already rely on it.

Adoption comes before monetization.

---

## Why This Matters

Get 50% of the population 10% better. Every year. That is generational growth.

Not 10 developers 500% better. That is happening. But it does not scale to the economy.

*"How do I save 5 hours a week?" "How do I save $700 a month?"*

Those are the real questions. This is how you answer them.

Alberta's **steel, lumber, and metals** industries represent over **2,500 companies** with a combined economic impact exceeding **$37 billion annually**.

| Sector | Companies | Economic Impact | Jobs Supported |
|--------|-----------|-----------------|----------------|
| Forestry & Wood Products | 676+ businesses, 40 major mills | $14 billion | 41,400 |
| Fabricated Metal Products | 1,871 establishments | $23.4B manufacturing sector | 16,600 |
| Primary & Machinery Manufacturing | 200+ facilities | Included above | 12,000+ |

Behind every one of these companies are dozens of systems that need to talk to each other just to get anything done: quoting software, inventory spreadsheets, accounting packages, project trackers, supplier portals, and government tender databases.

Any tool that helps a fabricator **create demand**, a mill **manufacture more efficiently**, or a contractor **cut costs** has multiplier effects across the entire province:

- **$4 billion** in forest product exports alone
- **$1.6 billion** in annual wages paid to forestry workers
- **70 communities** across Alberta that depend directly on these industries
- **$988 million** in tax revenue flowing back to the province

More contracts won. More jobs kept. More skill developed. More value staying here at home.

---

## Built for Trades, Not Tech

This is not another SaaS dashboard.

There is no new portal to babysit, no CRM ceremony, and no "AI transformation" theatre. The workspace runs locally, reads only what you authorize, and exposes practical procurement tools to the agent surface.

The owner should not have to care whether the answer came from a CSV, an API, a model endpoint, or an MCP tool. They should care that the right opportunities are visible before the deadline, the requirements are easier to understand, and the next action is clear.

---

## Technical Notes

MCP server:

- [`mcp-servers/canadabuys/server.py`](mcp-servers/canadabuys/server.py)
- [`mcp-servers/canadabuys/server_sse.py`](mcp-servers/canadabuys/server_sse.py) for hosted MCP over SSE plus REST/OpenAPI
- [`procurement_core/service.py`](procurement_core/service.py) for the shared Python procurement core
- [`procurement_core/e2b_bid_room.py`](procurement_core/e2b_bid_room.py) for live E2B bid-room sandbox processing

Smoke test:

- [`tests/test_canadabuys_mcp_smoke.py`](tests/test_canadabuys_mcp_smoke.py)
- [`tests/test_procurement_http_app.py`](tests/test_procurement_http_app.py)
- `python scripts/e2b_bid_room_smoke.py` for a live E2B sandbox test

Configuration:

- [`AGENTS.md`](AGENTS.md) for Codex/OpenClaw guidance
- [`mcp-servers/canadabuys/README.md`](mcp-servers/canadabuys/README.md) for server tools and environment variables
- [`docs/codex-setup.md`](docs/codex-setup.md) for local setup notes
- [`docs/workspace-alberta-hermes-install.md`](docs/workspace-alberta-hermes-install.md) for the branded Hermes / Raspberry Pi setup draft

Data and model sources:

- CanadaBuys open tender notices
- Alberta Purchasing Connection public opportunity API
- Cohere Command A+ via Cohere API
- CohereLabs Command A+ W4A4 on Hugging Face: <https://huggingface.co/CohereLabs/command-a-plus-05-2026-w4a4>

Image source notes live in [`docs/imagery-sources.md`](docs/imagery-sources.md).

---

## The Last Mile

Every efficiency gained by an Alberta fabricator, mill, or contractor ripples outward.

Faster quotes mean more bids submitted. Better visibility means fewer missed opportunities. Better tender triage means less wasted estimating time. Better Canadian AI infrastructure means less dependence in the places where dependence matters.

This is not replacing workers with AI. It is operational leverage for the people doing the actual work.

The last mile is where the real work lives. We are building the wiring.

**Canada is going to work.**

*Data sources: [Statistics Canada](https://www150.statcan.gc.ca), [Innovation Canada](https://ised-isde.canada.ca), [Alberta Forest Products Association](https://albertaforestproducts.ca), [Job Bank Canada](https://www.jobbank.gc.ca)*
