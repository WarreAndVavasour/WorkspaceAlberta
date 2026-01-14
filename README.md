# WorkspaceAlberta
## The Last Mile of Work

AI promised 5X productivity. Most small businesses got a chatbot that writes mediocre marketing copy.

The model isn't the bottleneck. The connection is.

Telecom companies spent billions on backbone infrastructure. But the value capture happened in the last mile—the wire to your house. Same pattern here. OpenAI, Anthropic, Google—they built the backbone. But the economic value is trapped in the connection between the model and the QuickBooks instance on a steel fabricator's laptop.

Wiring up your tools to AI costs $150/hour. You need a developer. Most small businesses will never do this. That's the gap. That's where the 5X productivity is hiding.

**WorkspaceAlberta solves the last mile**—pre-configured workspaces that already speak to the tools your industry uses. A steel fabricator and a lumber mill need different tool bundles. Generic AI assistants force them to do the integration work themselves. We don't.

---

## "Wouldn't It Be Great If..."

This is how you use it. You describe a problem:

> *"Wouldn't it be great if I could see all government contracts for steel fabrication in Alberta, filtered by ones we could actually bid on?"*

> *"Wouldn't it be great if I could find which customers are both overdue AND have meetings scheduled this week?"*

> *"Wouldn't it be great if I could pull our inventory spreadsheet and compare it to the materials list on that new RFP?"*

The AI already has permission to look. It pulls the data. Builds the report. Asks you when it gets stuck—not some support ticket black hole. Done.

---

## Why This Matters: The Math on Broad vs. Deep

Get 50% of the population 10% better. Every year. That's generational growth.

Not 10 developers 500% better. That's happening. But it doesn't scale to the economy.

A 10% productivity gain across 2,500 Alberta metal and lumber businesses is worth more to the provincial economy than a 500% gain for 50 tech companies. The multiplier effects are different—fabricators hire locally, buy locally, pay taxes locally. The velocity of money stays in the region.

*"How do I save 5 hours a week?" "How do I save $700 a month?"*

Those are the real questions. This is how you answer them.

---

## No New Subscription. No New Password. No New System to Learn.

Business owners don't need another app, another login, or another workflow builder that might write an OK-ish blog post. They need to solve actual problems.

WorkspaceAlberta is like Word, but for solving problems.

It's a program you open almost every day to work on one specific *"wouldn't it be great if..."* problem—the kind that's unique to your trade, your shop, your contracts.

---

## The Opportunity

Alberta's **Steel, Lumber, and Metals** industries represent over **2,500 companies** with a combined economic impact exceeding **$37 billion annually**.

| Sector | Companies | Economic Impact | Jobs Supported |
|--------|-----------|-----------------|----------------|
| Forestry & Wood Products | 676+ businesses, 40 major mills | $14 billion | 41,400 |
| Fabricated Metal Products | 1,871 establishments | $23.4B (mfg sector) | 16,600 |
| Primary & Machinery Manufacturing | 200+ facilities | Included above | 12,000+ |

Behind every one of these companies are dozens of systems that need to talk to each other just to get anything done: quoting software, inventory spreadsheets, accounting packages, project trackers, supplier portals, government tender databases.

Any tool that helps a fabricator **create demand**, a mill **manufacture more efficiently**, or a contractor **cut costs** has multiplier effects across the entire province:

- **$4 billion** in forest product exports alone—shipped to the US, China, Japan, and South Korea
- **$1.6 billion** in annual wages paid to forestry workers
- **70 communities** across Alberta that depend directly on these industries
- **$988 million** in tax revenue flowing back to the province

More contracts won. More jobs kept. More skill developed. More value staying here at home.

---

## What This Actually Does

WorkspaceAlberta removes the barrier between your business and an intelligent assistant that already understands your tools, your industry, and the federal contracts relevant to your work.

### Step 1: List Your Tools
Edit **`owner-tools-list.md`** with the software you actually use—QuickBooks, Slack, Google Drive, your ERP, whatever. No technical knowledge required.

### Step 2: Describe the Problem
Edit **`monthly-pain-point.md`** with one specific problem:
> *"I spend 6 hours every week manually checking CanadaBuys for steel contracts and comparing them to our inventory spreadsheet."*

### Step 3: Open and Work
Launch the workspace. Your assistant already knows your tools and has access to live federal tender data filtered for your industry. Ask it questions. Give it tasks. Solve the problem.

---

## Federal Contract Intelligence

The workspace includes direct integration with **CanadaBuys**, the federal government's procurement database. Your assistant can:

- Pull live tender notices for Steel, Lumber, and Aluminum across Alberta
- Filter opportunities by UNSPSC codes and industry keywords
- Analyze contract requirements against your actual capabilities
- Flag deadlines and compliance requirements before you miss them

---

## Built for Trades, Not Tech

This isn't another SaaS dashboard. There's no monthly fee, no login portal, no "upgrade to Pro" nonsense.

You download it. You open it. You work.

The workspace runs locally on your machine or in a cloud development environment. Your data stays yours. The AI reads your tools through secure, permissioned connections—it can see what you authorize and nothing else.

---

## Technical Details

For developers and IT teams who want to understand what's under the hood:

- **Generator Engine**: Reads your tool list and produces MCP (Model Context Protocol) configurations
- **MCP Servers**: Secure bridges that let the AI interact with business software (read spreadsheets, check calendars, query databases)
- **CanadaBuys Pipeline**: Python-based ETL that fetches, filters, and summarizes federal procurement data
- **Cursor/Codespaces**: Works in Cursor IDE locally or GitHub Codespaces in the cloud

```bash
# Generate workspace configuration
python generator/generator.py google_drive slack quickbooks stripe

# Run federal contract pipeline
python pipelines/canadabuys/pipeline.py --source open
```

Full technical documentation: [`CLAUDE.md`](CLAUDE.md)

---

## The Last Mile

Every efficiency gained by an Alberta fabricator, mill, or contractor ripples outward.

Faster quotes = more bids submitted. Better inventory = less waste. Automated compliance = fewer missed opportunities.

This isn't replacing workers with AI. It's operational leverage for the people doing the actual work.

The last mile is where the real work lives. We're building the wiring.

**Canada is going to work. Let's get busy.**

---

## License

MIT

---

*Data sources: [Statistics Canada](https://www150.statcan.gc.ca), [Innovation Canada](https://ised-isde.canada.ca), [Alberta Forest Products Association](https://albertaforestproducts.ca), [Job Bank Canada](https://www.jobbank.gc.ca)*
