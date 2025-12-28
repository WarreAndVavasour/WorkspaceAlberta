# WorkspaceAlberta: Specialized Workspace Generator for Primary Industries

WorkspaceAlberta is a specialized **workspace generator** that automates the creation of high-context, intelligent environments. It is specifically engineered to support businesses in Alberta's **federal priority industries** (Steel, Lumber, and Aluminum) by providing an assistant (primarily **Claude**) that is pre-configured to reason across both internal business tools and the **CanadaBuys** federal contract data pipeline.

This is a **generative environment factory** that uses the **Model Context Protocol (MCP)** to bridge the gap between advanced knowledge systems and industry-specific data.

## Core Capabilities

### 1. Automated Workspace Generation
The system programmatically constructs personalized environments (local Cursor workspaces or GitHub Codespaces) pre-loaded with:
*   **Intelligent Assistants**: Optimized for **Claude** (via the `anthropic.claude-code` extension) and Claude Code.
*   **Model Context Protocol (MCP)**: Pre-configured servers that allow your assistant to securely interact with your specific business stack.
*   **Industry Context**: Pre-defined rules and documentation tailored to Alberta's primary industrial sectors.

### 2. CanadaBuys Federal Data Integration
The generator includes built-in pipelines for the **CanadaBuys** federal program. This provides your assistant with direct access to:
*   **Live Tender Feeds**: Real-time government contract opportunities in Alberta.
*   **Industry Matching**: Automatic filtering for Steel, Lumber, and Aluminum UNSPSC codes and keywords.
*   **Expert Reasoning**: The ability for the assistant to analyze tender requirements against your company's actual capabilities and tools.

### 3. MCP-Powered Tool Connectivity
We leverage the **Model Context Protocol (MCP)** to grant your assistant secure access to your business tools. This allows the system to:
*   **Read/Write**: Interact with spreadsheets, calendars, and documentation.
*   **Integrate**: Connect disparate systems like QuickBooks, HubSpot, and Stripe.
*   **Automate**: Perform complex workflows directly within the workspace based on natural language instructions.

---

## For Business Owners: How It Works

WorkspaceAlberta removes the technical barrier to using advanced intelligent systems. We build the environment for you based on your unique business context.

### Step 1: Define Your Stack
Edit **`owner-tools-list.md`** and list every tool your business uses (e.g., Slack, Google Drive, QuickBooks, or custom internal systems). Our generator uses this to select the correct MCP servers for your workspace.

### Step 2: Identify the Pain Point
Edit **`monthly-pain-point.md`** and describe a specific business problem in plain language. 
*   *Example: "I need to analyze CanadaBuys steel tenders and compare them to our current inventory and pricing in Excel."*

### Step 3: Launch Your Workspace
The generator produces a tailored configuration. When you open this in Cursor or GitHub Codespaces, you have a **pre-configured assistant** that already knows your tools, your industry, and the specific federal data related to your goal.

---

## Technical Architecture

*   **Generator (`generator/`)**: The core engine that loads the 50-tool `catalog.json` and emits `.cursor/mcp.json`, `.env` templates, and `INTEGRATIONS.md`.
*   **Codespace Factory (`generator/codespace_generator.py`)**: Automates the creation of `devcontainer.json` and `.vscode/mcp.json` for one-click cloud environments.
*   **Federal Pipeline (`pipelines/canadabuys/`)**: A CKAN-integrated Python engine that fetches and filters federal tender notices for Alberta priority sectors.
*   **MCP SDK**: Every generated workspace includes the `@modelcontextprotocol/sdk` to facilitate tool-to-assistant communication.

---

## License
MIT
