#!/usr/bin/env bash
# Make elbowsupknivesout.warreandvavasour.com front the WorkspaceAlberta Cloud Run
# service via a Cloudflare Worker proxy bound as a custom domain. The Worker fetches
# the run.app origin directly, so SNI/SSL are handled correctly (fixes the 522 you get
# from a plain proxied CNAME).
#
# Usage:  CLOUDFLARE_API_TOKEN=xxx [CLOUDFLARE_ACCOUNT_ID=yyy] bash cf_elbows_endpoint.sh
set -euo pipefail

: "${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN}"
ZONE_NAME="warreandvavasour.com"
HOSTNAME="elbowsupknivesout.warreandvavasour.com"
ORIGIN="workspacealberta-jinwk3wvyq-nn.a.run.app"
SCRIPT_NAME="elbows-mcp"
API="https://api.cloudflare.com/client/v4"
auth=(-H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}")
jget() { grep -o "\"$1\":\"[^\"]*\"" | head -1 | cut -d'"' -f4; }

echo "==> verifying token"
curl -fsS "${auth[@]}" "${API}/user/tokens/verify" | grep -o '"status":"[a-z]*"' || true

echo "==> resolving zone + account"
zinfo=$(curl -fsS "${auth[@]}" "${API}/zones?name=${ZONE_NAME}")
ZONE_ID=$(echo "$zinfo" | grep -o '"id":"[a-f0-9]\{32\}"' | head -1 | cut -d'"' -f4)
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-$(echo "$zinfo" | grep -o '"account":{"id":"[a-f0-9]\{32\}"' | grep -o '[a-f0-9]\{32\}')}"
echo "    zone=${ZONE_ID}  account=${ACCOUNT_ID}"

echo "==> removing any existing DNS record for ${HOSTNAME}"
recs=$(curl -fsS "${auth[@]}" "${API}/zones/${ZONE_ID}/dns_records?name=${HOSTNAME}")
for rid in $(echo "$recs" | grep -o '"id":"[a-f0-9]\{32\}"' | cut -d'"' -f4); do
  curl -fsS -X DELETE "${auth[@]}" "${API}/zones/${ZONE_ID}/dns_records/${rid}" >/dev/null && echo "    deleted ${rid}"
done

echo "==> uploading Worker '${SCRIPT_NAME}'"
WORKER='addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  url.hostname = "'"${ORIGIN}"'";
  url.port = "";
  event.respondWith(fetch(new Request(url, event.request)));
});'
up=$(curl -fsS -X PUT "${auth[@]}" -H "Content-Type: application/javascript" --data "$WORKER" \
  "${API}/accounts/${ACCOUNT_ID}/workers/scripts/${SCRIPT_NAME}")
echo "    $(echo "$up" | grep -o '"success":[a-z]*' | head -1)"

echo "==> binding custom domain ${HOSTNAME}"
bind=$(curl -fsS -X PUT "${auth[@]}" -H "Content-Type: application/json" \
  --data "{\"zone_id\":\"${ZONE_ID}\",\"hostname\":\"${HOSTNAME}\",\"service\":\"${SCRIPT_NAME}\",\"environment\":\"production\"}" \
  "${API}/accounts/${ACCOUNT_ID}/workers/domains") || true
echo "    $(echo "$bind" | grep -o '"success":[a-z]*\|"message":"[^"]*"' | head -2 | tr '\n' ' ')"

echo "==> done; cert provisions in ~1-2 min."
