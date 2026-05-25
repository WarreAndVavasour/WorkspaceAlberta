# Workspace Alberta custom Hermes installation

This document is a first draft for a branded Hermes Agent setup that can run on a Raspberry Pi as a local Workspace Alberta operator console.

The goal is not to fork Hermes or hide what it is. The goal is to ship a practical, preconfigured Workspace Alberta experience:

- the Hermes dashboard opens with Workspace Alberta colors and language
- the CanadaBuys / Alberta procurement MCP tools are already wired in
- the local browser can launch directly into the dashboard
- secrets stay local and are never committed to this repository
- the setup can be repeated on another Raspberry Pi without rebuilding everything by hand

This is the white-label layer around the procurement workspace.

---

## Out-of-box Pi install

For a single-purpose Workspace Alberta appliance, the repo includes an installer that turns a fresh Raspberry Pi OS / Debian user account into the branded default experience.

From a fresh Pi desktop session:

```bash
git clone https://github.com/HarleyCoops/WorkspaceAlberta.git ~/WorkspaceAlberta
cd ~/WorkspaceAlberta
chmod +x installer/install-workspace-alberta-pi.sh
./installer/install-workspace-alberta-pi.sh
```

The installer does the repeatable setup work:

- installs baseline OS packages: `git`, `curl`, `python3`, `python3-venv`, `chromium`
- installs Hermes if `hermes` is not already on `PATH`
- creates the repo `.venv` and runs the CanadaBuys MCP smoke test
- copies `hermes/dashboard-themes/workspace-alberta.yaml` into `~/.hermes/dashboard-themes/`
- sets `dashboard.theme` to `workspace-alberta`
- enables the local API server on `127.0.0.1:8642`
- patches the local dashboard browser title to `WorkspaceAlberta`
- installs user-level systemd services for the dashboard and gateway
- enables service linger so the appliance can run without an active SSH session
- installs a Chromium autostart launcher for the desktop session

After install, the default local endpoints are:

```text
Dashboard: http://127.0.0.1:9119/
API:       http://127.0.0.1:8642/v1
Model:     hermes-agent
```

Useful service commands:

```bash
systemctl --user status workspace-alberta-dashboard.service
systemctl --user status workspace-alberta-gateway.service
systemctl --user restart workspace-alberta-dashboard.service
systemctl --user restart workspace-alberta-gateway.service
journalctl --user -u workspace-alberta-dashboard.service -f
```

Installer knobs:

```bash
# Do not install Chromium desktop autostart
INSTALL_KIOSK=0 ./installer/install-workspace-alberta-pi.sh

# Use non-default ports
DASHBOARD_PORT=9120 API_PORT=8650 ./installer/install-workspace-alberta-pi.sh

# Do not patch the local dashboard HTML title
PATCH_TITLE=0 ./installer/install-workspace-alberta-pi.sh
```

For a shipping unit, pre-run this installer on the Pi image, then add the user's provider credentials locally through `hermes setup`, `hermes model`, or `~/.hermes/.env`. Never bake real API keys into the repo or image template.

---

## Target experience

A small business owner or estimator should be able to power on the Pi and land at:

```text
http://127.0.0.1:9119/
```

They should see a Workspace Alberta branded Hermes dashboard and be able to ask practical questions like:

- What CanadaBuys opportunities are open right now?
- What Alberta postings close this week?
- Which tenders fit what this shop actually does?
- What should we read first?
- What should we ignore?
- Wouldn't it be great if I got a daily bid brief without checking another portal?

---

## Recommended architecture

Keep the custom layer separate from upstream Hermes.

```text
Raspberry Pi
├── Debian / Raspberry Pi OS
├── Chromium
├── Hermes Agent
│   ├── dashboard running on 127.0.0.1:9119
│   ├── API server running on 127.0.0.1:8642
│   └── local Hermes profile: workspace-alberta
└── WorkspaceAlberta repo
    ├── procurement MCP server
    ├── branded dashboard theme
    ├── setup documentation
    ├── installer scripts and user-level systemd service templates
    └── Chromium autostart launcher
```

Use a Hermes profile for the branded installation when possible:

```bash
hermes profile create workspace-alberta
```

That lets the branded setup have its own config, skills, memory, tool settings, and theme without changing the default Hermes profile.

---

## Prerequisites

On the Raspberry Pi:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv chromium
```

Install Hermes Agent using the official installer or an existing local Hermes checkout.

Then verify Hermes works:

```bash
hermes doctor
hermes --version
```

Clone this repository:

```bash
git clone https://github.com/HarleyCoops/WorkspaceAlberta.git ~/WorkspaceAlberta
cd ~/WorkspaceAlberta
```

Install the Workspace Alberta Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the MCP smoke test:

```bash
python3 -m unittest tests.test_canadabuys_mcp_smoke
```

---

## Install the branded dashboard theme

Hermes dashboard themes are YAML files stored in:

```text
~/.hermes/dashboard-themes/
```

Copy the Workspace Alberta theme template from this repo:

```bash
mkdir -p ~/.hermes/dashboard-themes
cp hermes/dashboard-themes/workspace-alberta.yaml ~/.hermes/dashboard-themes/workspace-alberta.yaml
```

Set it as the active dashboard theme:

```bash
hermes config set dashboard.theme workspace-alberta
```

Start or restart the dashboard:

```bash
hermes dashboard --host 127.0.0.1 --port 9119 --tui --no-open
```

Open it in Chromium:

```bash
chromium --new-window http://127.0.0.1:9119/
```

If the theme does not appear, restart the dashboard process. Dashboard config and theme files are read by the running dashboard server.

---

## Theme file shape

A minimal Hermes dashboard theme looks like this:

```yaml
name: workspace-alberta
label: Workspace Alberta
description: Branded Workspace Alberta operator console

palette:
  background:
    hex: "#071417"
    alpha: 1
  midground:
    hex: "#F4E9D8"
    alpha: 1
  foreground:
    hex: "#FFFFFF"
    alpha: 0
  warmGlow: "rgba(242, 165, 65, 0.32)"
  noiseOpacity: 0.85

layout:
  radius: "0.9rem"
  density: comfortable
```

The full template in `hermes/dashboard-themes/workspace-alberta.yaml` also includes typography, color overrides, background gradients, and custom CSS hooks.

---

## Enable the local Hermes API server

External web UIs can talk to Hermes through its OpenAI-compatible local API server.

Add these values to the Hermes `.env` file, or set them through your normal Hermes configuration process:

```text
API_SERVER_ENABLED=true
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
API_SERVER_MODEL_NAME=hermes-agent
```

Start the gateway:

```bash
hermes gateway run
```

Verify the API server:

```bash
curl http://127.0.0.1:8642/health
curl http://127.0.0.1:8642/v1/models
```

For a local-only Pi, keep the API server bound to `127.0.0.1`. Do not expose it on `0.0.0.0` unless you also configure an API key, firewall rules, and a clear network trust boundary.

---

## Configure the procurement MCP server

Workspace Alberta's primary integration is the procurement MCP server.

The server entry point is:

```text
mcp-servers/canadabuys/server.py
```

Run it directly for a quick check:

```bash
python3 mcp-servers/canadabuys/server.py
```

Use the existing Cursor/OpenCode configs in the repo as the source of truth for exact MCP wiring:

```text
.cursor/mcp.json
opencode.json
```

For Hermes MCP setup, use Hermes' MCP commands so the configuration lands in the active Hermes profile:

```bash
hermes mcp add workspace-alberta-procurement --command "python3 ~/WorkspaceAlberta/mcp-servers/canadabuys/server.py"
hermes mcp test workspace-alberta-procurement
hermes mcp list
```

If the command form changes, keep this document in sync with the working `.cursor/mcp.json` and `opencode.json` project configs.

---

## Secrets and local credentials

Do not commit secrets to this repository.

Use local-only files for credentials:

```text
~/.hermes/.env
~/.hermes/profiles/workspace-alberta/.env
```

Examples of values that must stay local:

```text
GITHUB_TOKEN
COHERE_API_KEY
HF_TOKEN
GOOGLE_CLIENT_SECRET
GOOGLE_TOKEN
E2B_API_KEY
```

Commit examples and placeholders only:

```text
.env.example
config.yaml.template
```

Before pushing changes, check that no local secret files were staged:

```bash
git status --short
git diff --cached
```

---

## Optional kiosk-style launch

For an appliance-style Pi, start the dashboard and open Chromium on boot.

A future installer can turn this into systemd user services. The manual commands are:

```bash
hermes dashboard --host 127.0.0.1 --port 9119 --tui --no-open
hermes gateway run
chromium --new-window http://127.0.0.1:9119/
```

For a kiosk feel, Chromium can be launched with:

```bash
chromium --kiosk http://127.0.0.1:9119/
```

Use kiosk mode only after the setup is stable, because it is less convenient while debugging.

---

## First-boot checklist

1. Install system dependencies.
2. Install Hermes Agent.
3. Clone `HarleyCoops/WorkspaceAlberta`.
4. Install Python requirements.
5. Run the MCP smoke test.
6. Copy `hermes/dashboard-themes/workspace-alberta.yaml` into `~/.hermes/dashboard-themes/`.
7. Set `dashboard.theme` to `workspace-alberta`.
8. Enable the local Hermes API server on `127.0.0.1:8642`.
9. Add and test the Workspace Alberta procurement MCP server.
10. Launch the dashboard at `127.0.0.1:9119`.
11. Open Chromium to the dashboard.
12. Add only local secrets; never commit them.

---

## Future installer shape

A future `installer/install-workspace-alberta.sh` can automate the repeatable parts:

```text
installer/
├── install-workspace-alberta.sh
├── pi-first-boot.sh
└── systemd/
    ├── workspace-alberta-dashboard.service
    └── workspace-alberta-gateway.service
```

The installer should:

- check that it is running on Linux / Raspberry Pi OS
- install safe apt dependencies
- verify Hermes is installed
- copy the dashboard theme
- configure the Hermes profile
- install MCP wiring
- write `.env.example`, not real secrets
- run the MCP smoke test
- print the local dashboard URL

It should not:

- paste or print API keys
- commit user credentials
- expose the API server to the network by default
- overwrite an existing Hermes profile without making a backup

---

## Brand direction

The Workspace Alberta theme should feel like:

- Canadian industrial capability
- practical operator console, not generic SaaS
- Alberta manufacturing, forestry, steel, trades, and procurement
- dark pine / black-green base
- warm prairie amber action color
- cream text for readability
- simple language around real work

The brand promise remains:

> Wouldn't it be great if Canadian firms could see the right public work before the deadline was already too close?

The branded Hermes setup is one way to make that sentence operational.
