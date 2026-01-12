# WorkspaceAlberta Demo

**The last mile of work, solved.**

This workspace comes pre-configured with AI tools that understand Alberta's Steel, Lumber, and Aluminum industries.

## Quick Start

1. Open this folder in VS Code
2. Accept the MCP server trust prompts
3. Open Copilot Chat (Ctrl+Alt+I)
4. Ask: *"What government contracts are available for steel fabrication?"*

## What's Included

### MCP Servers (Pre-configured)

| Server | What it does |
|--------|-------------|
| **canadabuys** | Search federal government contracts filtered for Alberta + Steel/Lumber/Aluminum |
| **filesystem** | Read and analyze your local files |
| **memory** | Remember context across conversations |

### Example Questions

Try these in Copilot Chat:

- "Show me lumber contracts closing in the next 2 weeks"
- "Get details on contract [reference number]"
- "Summarize current opportunities by industry"
- "Compare my capabilities to this RFP" (share your capabilities first)

## The "Wouldn't It Be Great If..." Workflow

Describe your problem in plain English:

> "Wouldn't it be great if I could see all steel fabrication contracts in Alberta that we could actually bid on, sorted by deadline?"

The AI already has access to CanadaBuys. It will pull the data, filter it, and show you results.

## How This Works

This workspace uses **Model Context Protocol (MCP)** to connect AI directly to your business tools. Instead of copy-pasting data into ChatGPT, the AI can:

1. Search live government contract databases
2. Read your local spreadsheets and documents
3. Remember what you've discussed

No new app. No new login. Just AI that can finally see your business.

## Next Steps

- [ ] Run `python pipelines/canadabuys/pipeline.py --source open` to refresh contract data
- [ ] Add your own files to analyze
- [ ] Describe your "wouldn't it be great if..." problem

---

**Canada is going to work.**
