#!/usr/bin/env bash
set -euo pipefail

# Workspace Alberta out-of-box Hermes appliance installer.
# Run from the root of the WorkspaceAlberta repo on Raspberry Pi OS / Debian.

APP_NAME="WorkspaceAlberta"
THEME_NAME="workspace-alberta"
DASHBOARD_PORT="${DASHBOARD_PORT:-9119}"
API_PORT="${API_PORT:-8642}"
INSTALL_KIOSK="${INSTALL_KIOSK:-1}"
PATCH_TITLE="${PATCH_TITLE:-1}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33mWARN:\033[0m %s\n' "$*"; }

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
}

log "Installing OS packages"
if require_command apt-get; then
  sudo apt-get update
  sudo apt-get install -y git curl python3 python3-pip python3-venv chromium
else
  warn "apt-get not found; install git, curl, python3, python3-venv, and chromium manually."
fi

log "Checking Hermes CLI"
if ! require_command hermes; then
  warn "Hermes CLI is not installed. Installing with the official installer."
  curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi

if ! require_command hermes; then
  echo "Hermes still was not found on PATH. Open a new shell or add ~/.local/bin to PATH, then rerun this script." >&2
  exit 1
fi

log "Installing Workspace Alberta Python dependencies in repo venv"
cd "$REPO_DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest tests.test_canadabuys_mcp_smoke

log "Installing Hermes dashboard theme"
mkdir -p "$HERMES_HOME/dashboard-themes"
cp "$REPO_DIR/hermes/dashboard-themes/$THEME_NAME.yaml" "$HERMES_HOME/dashboard-themes/$THEME_NAME.yaml"
hermes config set dashboard.theme "$THEME_NAME"

log "Configuring local Hermes API server"
ENV_FILE="$(hermes config env-path 2>/dev/null || true)"
if [ -z "$ENV_FILE" ]; then
  ENV_FILE="$HERMES_HOME/.env"
fi
mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"
set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys
path, key, value = map(str, sys.argv[1:])
p = Path(path)
lines = p.read_text().splitlines()
p.write_text("\n".join(f"{key}={value}" if line.startswith(f"{key}=") else line for line in lines) + "\n")
PY
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}
set_env API_SERVER_ENABLED true
set_env API_SERVER_HOST 127.0.0.1
set_env API_SERVER_PORT "$API_PORT"
set_env API_SERVER_MODEL_NAME hermes-agent

log "Patching local browser tab title"
if [ "$PATCH_TITLE" = "1" ]; then
  HERMES_ROOT="$HERMES_HOME/hermes-agent"
  INDEX_HTML="$HERMES_ROOT/web/index.html"
  if [ -f "$INDEX_HTML" ]; then
    python3 - "$INDEX_HTML" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
for old in ["Hermes Agent - Dashboard", "Hermes Agent"]:
    text = text.replace(f"<title>{old}</title>", "<title>WorkspaceAlberta</title>")
p.write_text(text)
PY
    echo "Patched $INDEX_HTML"
  else
    warn "Could not find $INDEX_HTML; skipping browser title patch."
  fi
fi

log "Installing user systemd services"
mkdir -p "$USER_SYSTEMD_DIR"
export WORKSPACE_ALBERTA_REPO="$REPO_DIR"
export WORKSPACE_ALBERTA_HERMES_HOME="$HERMES_HOME"
export WORKSPACE_ALBERTA_DASHBOARD_PORT="$DASHBOARD_PORT"
export WORKSPACE_ALBERTA_API_PORT="$API_PORT"
envsubst_or_sed() {
  local src="$1" dst="$2"
  python3 - "$src" "$dst" <<'PY'
from pathlib import Path
import os, sys
src, dst = map(Path, sys.argv[1:])
text = src.read_text()
for key, value in os.environ.items():
    text = text.replace("${" + key + "}", value)
dst.write_text(text)
PY
}
envsubst_or_sed "$REPO_DIR/installer/systemd/workspace-alberta-dashboard.service" "$USER_SYSTEMD_DIR/workspace-alberta-dashboard.service"
envsubst_or_sed "$REPO_DIR/installer/systemd/workspace-alberta-gateway.service" "$USER_SYSTEMD_DIR/workspace-alberta-gateway.service"
systemctl --user daemon-reload
systemctl --user enable workspace-alberta-dashboard.service
systemctl --user enable workspace-alberta-gateway.service
systemctl --user restart workspace-alberta-dashboard.service
systemctl --user restart workspace-alberta-gateway.service || warn "Gateway service did not start; check model/API configuration and ~/.hermes/.env."

log "Allowing services to survive logout"
if require_command loginctl; then
  sudo loginctl enable-linger "$USER" || warn "Could not enable linger. User services may stop after logout."
fi

if [ "$INSTALL_KIOSK" = "1" ]; then
  log "Installing Chromium autostart launcher"
  mkdir -p "$AUTOSTART_DIR" "$HOME/.local/bin"
  cp "$REPO_DIR/installer/workspace-alberta-kiosk.sh" "$HOME/.local/bin/workspace-alberta-kiosk.sh"
  chmod +x "$HOME/.local/bin/workspace-alberta-kiosk.sh"
  python3 - "$REPO_DIR/installer/workspace-alberta-kiosk.desktop" "$AUTOSTART_DIR/workspace-alberta-kiosk.desktop" "$HOME" <<'PY'
from pathlib import Path
import sys
src, dst, home = sys.argv[1:]
text = Path(src).read_text().replace("${HOME}", home)
Path(dst).write_text(text)
PY
fi

log "Verifying dashboard"
for i in $(seq 1 30); do
  code="$(curl -s -o /tmp/workspace-alberta-dashboard.html -w '%{http_code}' "http://127.0.0.1:${DASHBOARD_PORT}/" || true)"
  if [ "$code" = "200" ]; then
    echo "Dashboard HTTP: $code"
    break
  fi
  sleep 1
done
curl -s -o /tmp/workspace-alberta-themes.json "http://127.0.0.1:${DASHBOARD_PORT}/api/dashboard/themes" || true
python3 - <<PY
import json
from pathlib import Path
p = Path('/tmp/workspace-alberta-themes.json')
if p.exists() and p.read_text().strip():
    data = json.loads(p.read_text())
    print('Active theme:', data.get('active'))
    print('Workspace Alberta available:', any(t.get('name') == '$THEME_NAME' for t in data.get('themes', [])))
PY

cat <<EOF

Workspace Alberta appliance setup complete.

Dashboard:
  http://127.0.0.1:${DASHBOARD_PORT}/

Local API server:
  http://127.0.0.1:${API_PORT}/v1

Services:
  systemctl --user status workspace-alberta-dashboard.service
  systemctl --user status workspace-alberta-gateway.service

Open dashboard now:
  chromium --new-window http://127.0.0.1:${DASHBOARD_PORT}/
EOF
