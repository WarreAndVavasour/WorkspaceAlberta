#!/usr/bin/env bash
set -euo pipefail

# Put a WorkspaceAlberta Pro subscriber key on this machine and wire it into
# the local MCP clients.
#
# The hosted server gates six Pro tools behind an `Authorization: Bearer
# wa_live_...` header (see procurement_core/auth.py). Nothing else in the
# install path supplies that header, so without this step a leased terminal
# talks to the free tier only.
#
# Usage:
#   ./installer/configure-subscriber-key.sh [wa_live_...]
#   WA_API_KEY=wa_live_... ./installer/configure-subscriber-key.sh
#
# With no argument and no WA_API_KEY the script prompts. Run it again at any
# time to rotate the key.
#
# Environment:
#   WA_API_KEY   subscriber key; prompted for when unset
#   WA_MCP_URL   endpoint override (default: the hosted production endpoint)
#   WA_SKIP_VERIFY=1  write the key without calling /me (offline staging)

DEFAULT_URL="https://elbowsupknivesout.warreandvavasour.com/mcp"
MCP_URL="${WA_MCP_URL:-$DEFAULT_URL}"
BASE_URL="${MCP_URL%/mcp}"
CONFIG_DIR="${WA_CONFIG_DIR:-$HOME/.config/workspacealberta}"
CREDENTIALS_FILE="$CONFIG_DIR/credentials"
MCP_CONFIG_FILE="$CONFIG_DIR/mcp.json"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN:\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- collect key

KEY="${1:-${WA_API_KEY:-}}"
if [ -z "$KEY" ] && [ -r "$CREDENTIALS_FILE" ]; then
  EXISTING="$(sed -n 's/^WA_API_KEY=//p' "$CREDENTIALS_FILE" | head -1)"
  if [ -n "$EXISTING" ]; then
    log "A key is already configured in $CREDENTIALS_FILE"
    printf 'Press Enter to keep it, or paste a new key to replace it: '
    read -r REPLACEMENT || REPLACEMENT=""
    KEY="${REPLACEMENT:-$EXISTING}"
  fi
fi
if [ -z "$KEY" ]; then
  echo "WorkspaceAlberta Pro key (from your subscription email; starts with wa_live_)."
  echo "Leave blank to skip and stay on the free tier."
  printf 'Key: '
  read -r KEY || KEY=""
fi

if [ -z "$KEY" ]; then
  log "No key supplied. This machine stays on the free tier."
  echo "Subscribe at https://buy.stripe.com/14AfZieZmcb2eYB5v1g7e0a, then re-run:"
  echo "  ./installer/configure-subscriber-key.sh"
  exit 0
fi

case "$KEY" in
  wa_live_*) ;;
  *) fail "That does not look like a subscriber key — it must start with wa_live_." ;;
esac

# --------------------------------------------------------------------- verify

if [ "${WA_SKIP_VERIFY:-0}" != "1" ]; then
  log "Verifying the key against $BASE_URL/me"
  BODY_FILE="$(mktemp)"
  trap 'rm -f "$BODY_FILE"' EXIT
  CODE="$(curl -sS --max-time 30 -o "$BODY_FILE" -w '%{http_code}' \
    -H "Authorization: Bearer $KEY" "$BASE_URL/me" || echo 000)"
  case "$CODE" in
    200)
      python3 - "$BODY_FILE" <<'PY' || true
import json, sys
with open(sys.argv[1]) as handle:
    data = json.load(handle)
print(f"  status: {data.get('status')}  plan: {data.get('plan')}  email: {data.get('email') or '(none on file)'}")
PY
      ;;
    401) fail "The server does not recognise that key. Check it against your subscription email." ;;
    402) fail "That key is known but the subscription is not active. Check billing in Stripe." ;;
    000) warn "Could not reach $BASE_URL — writing the key unverified. Re-run once this machine is online." ;;
    *)   warn "Unexpected HTTP $CODE from /me — writing the key unverified." ;;
  esac
fi

# ------------------------------------------------------------------ write key

log "Writing credentials to $CREDENTIALS_FILE"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"
umask 077
cat > "$CREDENTIALS_FILE" <<EOF
# WorkspaceAlberta subscriber credentials. Owner-readable only; never commit.
WA_API_KEY=$KEY
WA_MCP_URL=$MCP_URL
EOF
chmod 600 "$CREDENTIALS_FILE"

log "Writing MCP client config to $MCP_CONFIG_FILE"
python3 - "$MCP_CONFIG_FILE" "$MCP_URL" "$KEY" <<'PY'
import json, sys
path, url, key = sys.argv[1:]
with open(path, "w") as handle:
    json.dump({"mcpServers": {"workspacealberta": {
        "type": "http",
        "url": url,
        "headers": {"Authorization": f"Bearer {key}"},
    }}}, handle, indent=2)
    handle.write("\n")
PY
chmod 600 "$MCP_CONFIG_FILE"

# -------------------------------------------------------------- wire into CLIs

if command -v claude >/dev/null 2>&1; then
  log "Registering with Claude Code (user scope)"
  claude mcp remove workspacealberta --scope user >/dev/null 2>&1 || true
  if claude mcp add --scope user --transport http workspacealberta "$MCP_URL" \
      --header "Authorization: Bearer $KEY" >/dev/null 2>&1; then
    echo "  claude mcp list  # to confirm"
  else
    warn "Could not register with Claude Code. Point it at $MCP_CONFIG_FILE by hand."
  fi
fi

CURSOR_CONFIG="$HOME/.cursor/mcp.json"
if [ -d "$HOME/.cursor" ]; then
  log "Merging into $CURSOR_CONFIG"
  python3 - "$CURSOR_CONFIG" "$MCP_URL" "$KEY" <<'PY' || warn "Cursor config merge failed; edit $CURSOR_CONFIG by hand."
import json, os, sys
path, url, key = sys.argv[1:]
config = {}
if os.path.exists(path):
    try:
        with open(path) as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError):
        # Never clobber a config we cannot parse — bail and let the warning fire.
        raise SystemExit(1)
servers = config.setdefault("mcpServers", {})
servers["workspacealberta"] = {"url": url, "headers": {"Authorization": f"Bearer {key}"}}
with open(path, "w") as handle:
    json.dump(config, handle, indent=2)
    handle.write("\n")
PY
fi

cat <<EOF

Subscriber key configured.

  Credentials:  $CREDENTIALS_FILE  (chmod 600)
  MCP config:   $MCP_CONFIG_FILE

For Claude Desktop (no native HTTP transport), add to its config file:

  {
    "mcpServers": {
      "workspacealberta": {
        "command": "npx",
        "args": ["-y", "@warreandvavasour/workspace-alberta"],
        "env": { "WORKSPACEALBERTA_API_KEY": "$KEY" }
      }
    }
  }

Confirm Pro access at any time:

  curl -H "Authorization: Bearer \$WA_API_KEY" $BASE_URL/me
EOF
