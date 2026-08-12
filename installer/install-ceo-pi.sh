#!/usr/bin/env bash
set -euo pipefail

# WorkspaceAlberta CEO productivity terminal first-boot installer.
# Run on Raspberry Pi 5 16GB with Raspberry Pi OS / Ubuntu 24.04+.
#
# This installer sets up the hyperproductive CEO stack:
# - Tailscale for remote support
# - Codex CLI + ChatGPT desktop for AI-assisted work
# - OpenCode for MCP-first agent workflows
# - Optional WorkspaceAlberta repo clone with procurement agents
#
# Does NOT install or depend on OpenClaw / Clawdbot / openclaw.

# -----------------------------------------------------------------------------
# Configuration from environment (all optional with sensible defaults)
# -----------------------------------------------------------------------------
HOSTNAME_FQ="${HOSTNAME_FQ:-}"
SUPPORT_USER="${SUPPORT_USER:-support}"
TS_AUTHKEY="${TS_AUTHKEY:-}"
TS_TAGS="${TS_TAGS:-tag:wa-terminal,tag:wa-pi5}"
INSTALL_CODEX_DESKTOP="${INSTALL_CODEX_DESKTOP:-1}"
INSTALL_OPENCODE="${INSTALL_OPENCODE:-1}"
INSTALL_CODEX_CLI="${INSTALL_CODEX_CLI:-1}"
INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-1}"
INSTALL_HERMES_APPLIANCE="${INSTALL_HERMES_APPLIANCE:-0}"
CLONE_REPO="${CLONE_REPO:-1}"
SKIP_APT_UPGRADE="${SKIP_APT_UPGRADE:-0}"

# -----------------------------------------------------------------------------
# Helpers (match style of install-workspace-alberta-pi.sh)
# -----------------------------------------------------------------------------
log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33mWARN:\033[0m %s\n' "$*"; }
err() { printf '\n\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

require_command() {
  command -v "$1" >/dev/null 2>&1
}

# Detect architecture for package downloads
detect_arch() {
  local arch
  arch="$(uname -m)"
  case "$arch" in
    aarch64|arm64) echo "arm64" ;;
    x86_64|amd64) echo "amd64" ;;
    *) echo "unknown" ;;
  esac
}

# -----------------------------------------------------------------------------
# Root check — most operations need sudo
# -----------------------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
  err "Do not run this script as root. Run as a normal user with sudo access."
  exit 1
fi

log "WorkspaceAlberta CEO Terminal Installer"
log "Architecture: $(uname -m) / $(detect_arch)"

# -----------------------------------------------------------------------------
# APT: Update and upgrade system packages
# -----------------------------------------------------------------------------
log "Updating package lists"
sudo apt-get update

if [ "$SKIP_APT_UPGRADE" = "0" ]; then
  log "Running full system upgrade (set SKIP_APT_UPGRADE=1 to skip)"
  sudo apt-get full-upgrade -y
else
  log "Skipping full-upgrade (SKIP_APT_UPGRADE=1)"
fi

log "Installing baseline packages"
sudo apt-get install -y \
  curl \
  ca-certificates \
  tmux \
  vim \
  git \
  htop \
  jq \
  unattended-upgrades

log "Enabling unattended-upgrades"
sudo systemctl enable --now unattended-upgrades || warn "unattended-upgrades service may already be enabled"

# -----------------------------------------------------------------------------
# Hostname (optional)
# -----------------------------------------------------------------------------
if [ -n "$HOSTNAME_FQ" ]; then
  log "Setting hostname to: $HOSTNAME_FQ"
  sudo hostnamectl set-hostname "$HOSTNAME_FQ"
  hostnamectl
else
  log "No HOSTNAME_FQ set; keeping current hostname: $(hostname)"
fi

# -----------------------------------------------------------------------------
# Support user (for remote administration)
# -----------------------------------------------------------------------------
log "Checking support user: $SUPPORT_USER"
if id "$SUPPORT_USER" &>/dev/null; then
  log "Support user '$SUPPORT_USER' already exists"
else
  log "Creating support user: $SUPPORT_USER"
  sudo adduser --disabled-password --gecos "WorkspaceAlberta Support" "$SUPPORT_USER"
  sudo usermod -aG sudo "$SUPPORT_USER"
  log "Support user created and added to sudo group"
fi

# -----------------------------------------------------------------------------
# Tailscale
# -----------------------------------------------------------------------------
if [ "$INSTALL_TAILSCALE" = "1" ]; then
  log "Installing Tailscale"
  if require_command tailscale; then
    log "Tailscale already installed: $(tailscale --version | head -1)"
  else
    curl -fsSL https://tailscale.com/install.sh | sh
  fi

  sudo systemctl enable --now tailscaled || warn "tailscaled may already be running"

  if [ -n "$TS_AUTHKEY" ]; then
    log "Joining Tailscale with provided auth key"
    ts_args=(--authkey="$TS_AUTHKEY" --ssh)
    if [ -n "$HOSTNAME_FQ" ]; then
      ts_args+=(--hostname="$HOSTNAME_FQ")
    fi
    if [ -n "$TS_TAGS" ]; then
      ts_args+=(--advertise-tags="$TS_TAGS")
    fi
    sudo tailscale up "${ts_args[@]}"
    log "Tailscale connected"
  else
    warn "No TS_AUTHKEY provided. Tailscale installed but not joined."
    warn "To join interactively, run:"
    if [ -n "$HOSTNAME_FQ" ]; then
      warn "  sudo tailscale up --hostname=\"$HOSTNAME_FQ\" --advertise-tags=\"$TS_TAGS\" --ssh"
    else
      warn "  sudo tailscale up --advertise-tags=\"$TS_TAGS\" --ssh"
    fi
  fi
else
  log "Skipping Tailscale installation (INSTALL_TAILSCALE=0)"
fi

# -----------------------------------------------------------------------------
# Codex CLI
# -----------------------------------------------------------------------------
if [ "$INSTALL_CODEX_CLI" = "1" ]; then
  log "Installing Codex CLI"
  if require_command codex; then
    log "Codex CLI already installed"
  else
    if curl -fsSL https://chatgpt.com/codex/install.sh | sh; then
      log "Codex CLI installed via official script"
    else
      warn "Official Codex install script failed; trying npm fallback"
      if require_command npm; then
        npm install -g @openai/codex || warn "npm install of @openai/codex failed"
      else
        warn "npm not found; install Node.js and run: npm install -g @openai/codex"
      fi
    fi
  fi

  # Ensure ~/.local/bin is on PATH for this session
  if [ -d "$HOME/.local/bin" ]; then
    export PATH="$HOME/.local/bin:$PATH"
  fi
else
  log "Skipping Codex CLI installation (INSTALL_CODEX_CLI=0)"
fi

# -----------------------------------------------------------------------------
# ChatGPT / Codex Desktop (Linux ARM64/AMD64)
# -----------------------------------------------------------------------------
if [ "$INSTALL_CODEX_DESKTOP" = "1" ]; then
  log "Installing ChatGPT / Codex Desktop"

  arch="$(detect_arch)"
  case "$arch" in
    arm64)
      deb_url="https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_arm64.deb"
      deb_file="/tmp/chatgpt_arm64.deb"
      ;;
    amd64)
      deb_url="https://persistent.oaistatic.com/codex-app-prod/linux/deb/latest/chatgpt_amd64.deb"
      deb_file="/tmp/chatgpt_amd64.deb"
      ;;
    *)
      warn "Unknown architecture '$arch'; skipping ChatGPT desktop install"
      deb_url=""
      ;;
  esac

  if [ -n "$deb_url" ]; then
    # Check if already installed
    if dpkg -l | grep -q "chatgpt"; then
      log "ChatGPT desktop package already installed"
    else
      log "Downloading ChatGPT desktop for $arch"
      curl -fsSL -o "$deb_file" "$deb_url"

      log "Installing ChatGPT desktop package"
      # Note: On Raspberry Pi OS Bookworm this may show warnings if OS is older than officially supported
      sudo apt-get install -y "$deb_file" || {
        warn "apt-get install failed; trying dpkg + apt-get -f install"
        sudo dpkg -i "$deb_file" || true
        sudo apt-get install -f -y
      }

      rm -f "$deb_file"
      log "ChatGPT desktop installed"
    fi
  fi
else
  log "Skipping ChatGPT / Codex desktop installation (INSTALL_CODEX_DESKTOP=0)"
fi

# -----------------------------------------------------------------------------
# OpenCode
# -----------------------------------------------------------------------------
if [ "$INSTALL_OPENCODE" = "1" ]; then
  log "Installing OpenCode"
  if require_command opencode; then
    log "OpenCode already installed"
  else
    curl -fsSL https://opencode.ai/install | bash || warn "OpenCode install script failed"
  fi

  # Ensure ~/.local/bin is on PATH
  if [ -d "$HOME/.local/bin" ]; then
    export PATH="$HOME/.local/bin:$PATH"
  fi

  log "Note: opencode.json already exists in the WorkspaceAlberta repo with MCP/procurement agent config"
else
  log "Skipping OpenCode installation (INSTALL_OPENCODE=0)"
fi

# -----------------------------------------------------------------------------
# Clone WorkspaceAlberta repo (optional)
# -----------------------------------------------------------------------------
REPO_DIR="$HOME/WorkspaceAlberta"

if [ "$CLONE_REPO" = "1" ]; then
  log "Checking WorkspaceAlberta repo"
  if [ -d "$REPO_DIR/.git" ]; then
    log "Repo already exists at $REPO_DIR"
    log "Pulling latest changes"
    git -C "$REPO_DIR" pull --ff-only || warn "Could not pull; may have local changes"
  else
    log "Cloning WorkspaceAlberta to $REPO_DIR"
    git clone https://github.com/HarleyCoops/WorkspaceAlberta.git "$REPO_DIR"
  fi
else
  log "Skipping repo clone (CLONE_REPO=0)"
fi

# -----------------------------------------------------------------------------
# Hermes appliance layer (optional, off by default for CEO stack)
# -----------------------------------------------------------------------------
if [ "$INSTALL_HERMES_APPLIANCE" = "1" ]; then
  log "Installing Hermes appliance layer"
  if [ -d "$REPO_DIR" ] && [ -x "$REPO_DIR/installer/install-workspace-alberta-pi.sh" ]; then
    cd "$REPO_DIR"
    ./installer/install-workspace-alberta-pi.sh
  else
    warn "Cannot install Hermes appliance: repo not cloned or installer not found"
    warn "Clone the repo first (CLONE_REPO=1) then run: $REPO_DIR/installer/install-workspace-alberta-pi.sh"
  fi
else
  log "Skipping Hermes appliance layer (INSTALL_HERMES_APPLIANCE=0)"
  log "Note: The Hermes installer remains available at:"
  log "  $REPO_DIR/installer/install-workspace-alberta-pi.sh"
fi

# -----------------------------------------------------------------------------
# Summary and next steps
# -----------------------------------------------------------------------------
log "Installation complete"

echo ""
echo "============================================================"
echo " WorkspaceAlberta CEO Terminal — Setup Summary"
echo "============================================================"
echo ""

# Hostname
echo "Hostname:       $(hostname)"
echo ""

# Tailscale
if [ "$INSTALL_TAILSCALE" = "1" ]; then
  if require_command tailscale; then
    ts_status="$(tailscale status 2>&1 || echo 'not connected')"
    if echo "$ts_status" | grep -q "Tailscale is stopped"; then
      echo "Tailscale:      installed but stopped"
    elif echo "$ts_status" | grep -qi "logged out"; then
      echo "Tailscale:      installed but not logged in"
    else
      ts_ip="$(tailscale ip -4 2>/dev/null || echo 'N/A')"
      echo "Tailscale:      connected"
      echo "  Tailscale IP: $ts_ip"
    fi
  else
    echo "Tailscale:      not installed"
  fi
else
  echo "Tailscale:      skipped"
fi
echo ""

# Codex CLI
if [ "$INSTALL_CODEX_CLI" = "1" ]; then
  if require_command codex; then
    codex_ver="$(codex --version 2>/dev/null || echo 'installed')"
    echo "Codex CLI:      $codex_ver"
  else
    echo "Codex CLI:      installed (may need new shell for PATH)"
  fi
else
  echo "Codex CLI:      skipped"
fi

# ChatGPT Desktop
if [ "$INSTALL_CODEX_DESKTOP" = "1" ]; then
  if dpkg -l 2>/dev/null | grep -q "chatgpt"; then
    echo "ChatGPT Desktop: installed"
  else
    echo "ChatGPT Desktop: not installed (may not support this OS)"
  fi
else
  echo "ChatGPT Desktop: skipped"
fi

# OpenCode
if [ "$INSTALL_OPENCODE" = "1" ]; then
  if require_command opencode; then
    oc_ver="$(opencode --version 2>/dev/null || echo 'installed')"
    echo "OpenCode:       $oc_ver"
  else
    echo "OpenCode:       installed (may need new shell for PATH)"
  fi
else
  echo "OpenCode:       skipped"
fi

# Repo
if [ -d "$REPO_DIR/.git" ]; then
  echo "Repo:           $REPO_DIR"
else
  echo "Repo:           not cloned"
fi

echo ""
echo "============================================================"
echo " Next Steps"
echo "============================================================"
echo ""
echo "1. Open a new terminal or run: source ~/.bashrc"
echo ""

if [ "$INSTALL_CODEX_DESKTOP" = "1" ]; then
  echo "2. Sign into ChatGPT Desktop:"
  echo "   - Launch 'ChatGPT' from the applications menu"
  echo "   - Sign in with your OpenAI account"
  echo ""
fi

if [ "$INSTALL_CODEX_CLI" = "1" ]; then
  echo "3. Authenticate Codex CLI:"
  echo "   codex"
  echo "   (Follow the browser sign-in flow)"
  echo ""
fi

if [ "$INSTALL_OPENCODE" = "1" ]; then
  echo "4. Authenticate OpenCode:"
  echo "   opencode"
  echo "   (Follow the provider auth flow)"
  echo ""
fi

if [ "$INSTALL_TAILSCALE" = "1" ] && [ -z "$TS_AUTHKEY" ]; then
  echo "5. Complete Tailscale setup:"
  echo "   sudo tailscale up --advertise-tags=\"$TS_TAGS\" --ssh"
  echo "   (Then approve the device in Tailscale admin console)"
  echo ""
fi

echo "6. Verify the setup:"
echo "   tailscale status"
echo "   codex --version"
echo "   opencode --version"
echo ""
echo "7. Run procurement tools (after cloning repo):"
echo "   cd $REPO_DIR"
echo "   python -m pip install -r requirements.txt"
echo "   python -m unittest tests.test_canadabuys_mcp_smoke"
echo ""
echo "============================================================"
