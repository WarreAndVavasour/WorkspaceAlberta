# CEO Productivity Terminal Setup

> **New to Raspberry Pi?** Start with [pi-out-of-box-setup.md](pi-out-of-box-setup.md) for the complete beginner's guide — hardware checklist, flashing the OS, and first boot. This document covers the software installer only.

This runbook covers first-boot setup for WorkspaceAlberta CEO productivity terminals built on Raspberry Pi 5 16GB.

The CEO stack focuses on hyperproductive AI-assisted workflows:

- **Tailscale** for secure remote support
- **Codex CLI** for AI pair programming from the terminal
- **ChatGPT / Codex Desktop** for conversational AI on the desktop
- **OpenCode** for MCP-first agent workflows
- **WorkspaceAlberta procurement agents** via the cloned repo

This installer is separate from the Hermes appliance stack. Use the Hermes installer (`installer/install-workspace-alberta-pi.sh`) if you need the branded dashboard and local gateway services.

---

## Prerequisites

- Raspberry Pi 5 16GB (or Ubuntu 24.04+ VM for testing)
- Fresh Raspberry Pi OS Bookworm or Ubuntu 24.04/26.04 ARM64
- Internet connection
- A non-root user with sudo access
- Optional: Tailscale auth key from the admin console

---

## Quick start

Clone the repo and run the installer:

```bash
git clone https://github.com/HarleyCoops/WorkspaceAlberta.git ~/WorkspaceAlberta
cd ~/WorkspaceAlberta
chmod +x installer/install-ceo-pi.sh
./installer/install-ceo-pi.sh
```

For automated provisioning with Tailscale:

```bash
export HOSTNAME_FQ="wa-pi5-acme-edmonton-01"
export TS_AUTHKEY="tskey-auth-..."
./installer/install-ceo-pi.sh
```

---

## Environment variables

All configuration is through environment variables. All are optional with sensible defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `HOSTNAME_FQ` | (none) | Fully qualified hostname for the device |
| `SUPPORT_USER` | `support` | Remote support user account |
| `TS_AUTHKEY` | (none) | Tailscale auth key for unattended join |
| `TS_TAGS` | `tag:wa-terminal,tag:wa-pi5` | Tailscale device tags |
| `INSTALL_CODEX_DESKTOP` | `1` | Install ChatGPT / Codex desktop app |
| `INSTALL_OPENCODE` | `1` | Install OpenCode CLI |
| `INSTALL_CODEX_CLI` | `1` | Install Codex CLI |
| `INSTALL_TAILSCALE` | `1` | Install and configure Tailscale |
| `INSTALL_HERMES_APPLIANCE` | `0` | Also run the Hermes appliance installer |
| `CLONE_REPO` | `1` | Clone WorkspaceAlberta to ~/WorkspaceAlberta |
| `SKIP_APT_UPGRADE` | `0` | Skip apt full-upgrade for faster re-runs |

---

## What it installs

### Baseline packages

```text
curl ca-certificates tmux vim git htop jq unattended-upgrades
```

Unattended-upgrades is enabled to keep security patches current.

### Support user

Creates the support user (default: `support`) if missing and adds to the sudo group. This matches the remote support model in `tailscale-pi-remote-support.md`.

### Tailscale

Installs via the official script:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

If `TS_AUTHKEY` is set, joins the tailnet automatically with Tailscale SSH enabled:

```bash
sudo tailscale up --authkey="$TS_AUTHKEY" --hostname="$HOSTNAME_FQ" --advertise-tags="$TS_TAGS" --ssh
```

If no auth key is provided, Tailscale is installed but not joined. Run the join command interactively after install.

### Codex CLI

Installs via the official script:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Falls back to npm if the shell script fails:

```bash
npm install -g @openai/codex
```

### ChatGPT / Codex Desktop

Downloads and installs the official Linux desktop app:

- ARM64: `chatgpt_arm64.deb`
- AMD64: `chatgpt_amd64.deb`

The desktop app is officially validated on Ubuntu 24.04/26.04, Debian 13, and Fedora. On Raspberry Pi OS Bookworm it may install but show warnings if the OS is older than officially supported.

Skip with `INSTALL_CODEX_DESKTOP=0`.

### OpenCode

Installs via the official script:

```bash
curl -fsSL https://opencode.ai/install | bash
```

The WorkspaceAlberta repo already includes `opencode.json` with MCP server and procurement agent configuration.

Skip with `INSTALL_OPENCODE=0`.

### WorkspaceAlberta repo

Clones to `~/WorkspaceAlberta` if not already present. If the repo exists, pulls the latest changes.

Skip with `CLONE_REPO=0`.

### Hermes appliance (optional)

Set `INSTALL_HERMES_APPLIANCE=1` to also run the existing Hermes installer after the CEO stack setup. This adds the branded dashboard, local API gateway, and kiosk autostart.

By default this is off (`0`) because the CEO stack is focused on direct AI tool access rather than the Hermes dashboard experience.

---

## First-login steps

After the installer completes, open a new terminal and complete these steps:

### 1. Sign into ChatGPT Desktop

Launch ChatGPT from the applications menu and sign in with your OpenAI account.

### 2. Authenticate Codex CLI

```bash
codex
```

Follow the browser sign-in flow to authenticate.

### 3. Authenticate OpenCode

```bash
opencode
```

Follow the provider authentication flow.

### 4. Complete Tailscale setup (if no auth key was provided)

```bash
sudo tailscale up --advertise-tags="tag:wa-terminal,tag:wa-pi5" --ssh
```

Then approve the device in the Tailscale admin console.

### 5. Install Python dependencies for procurement tools

```bash
cd ~/WorkspaceAlberta
python -m pip install -r requirements.txt
```

---

## Smoke checks

Verify the installation:

```bash
# System
hostname
hostnamectl

# Tailscale
tailscale status
tailscale ip -4

# AI tools
codex --version
opencode --version
dpkg -l | grep chatgpt

# Procurement MCP
cd ~/WorkspaceAlberta
python -m unittest tests.test_canadabuys_mcp_smoke
```

---

## Remote support

Once Tailscale is connected, support staff can reach the device:

```bash
tailscale ssh support@wa-pi5-acme-edmonton-01
tmux attach -t support || tmux new -s support
```

See `tailscale-pi-remote-support.md` for the full remote support runbook.

---

## Re-running the installer

The installer is idempotent for most operations:

- Skips packages that are already installed
- Skips Tailscale join if already connected
- Pulls latest repo changes instead of re-cloning

For faster re-runs during testing:

```bash
SKIP_APT_UPGRADE=1 ./installer/install-ceo-pi.sh
```

---

## Secrets

Do not commit secrets to the repository.

The installer never bakes auth keys into the image. `TS_AUTHKEY` is read from the environment at runtime and not stored anywhere.

For provisioning batches, use short-lived reusable Tailscale auth keys and revoke them after the batch is complete.

---

## Related docs

- [tailscale-pi-remote-support.md](tailscale-pi-remote-support.md) — Tailscale remote support runbook
- [../terminal-spec.md](../terminal-spec.md) — Pi 5 16GB hardware spec
- [../codex-setup.md](../codex-setup.md) — Codex and OpenCode repo configuration
- [../workspace-alberta-hermes-install.md](../workspace-alberta-hermes-install.md) — Hermes appliance setup (separate installer)
