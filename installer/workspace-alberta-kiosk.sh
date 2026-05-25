#!/usr/bin/env bash
set -euo pipefail

URL="${WORKSPACE_ALBERTA_DASHBOARD_URL:-http://127.0.0.1:9119/?brand=workspace-alberta}"

# Give the user service a moment to bind the dashboard port after login.
for _ in $(seq 1 60); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

exec chromium \
  --new-window "$URL" \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-infobars
