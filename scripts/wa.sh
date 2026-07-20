#!/usr/bin/env bash
# WorkspaceAlberta tester CLI — drives the hosted procurement endpoint like a real user.
#
# Usage:
#   scripts/wa.sh health
#   scripts/wa.sh profile "CWB-certified structural steel fab, Calgary AB" "Bow Valley Steel" "Calgary, Alberta"
#   scripts/wa.sh search "snow removal" Alberta
#   scripts/wa.sh brief
#   scripts/wa.sh matches
#   scripts/wa.sh deadlines 14
#   scripts/wa.sh details AB-2026-04073
#   scripts/wa.sh analyze MX-444058980566 "fit and top risks?"
#
# Override the target with: export WA_URL=http://127.0.0.1:8000
set -euo pipefail

WA_URL="${WA_URL:-https://elbowsupknivesout.warreandvavasour.com}"
cmd="${1:-help}"; shift || true

post() { curl -s -X POST "$WA_URL$1" -H "Content-Type: application/json" -d "$2"; }
get()  { curl -s "$WA_URL$1"; }
show() { # pull the markdown "content" field out of the JSON envelope, fall back to raw
  python3 -c 'import sys,json
try:
    d=json.load(sys.stdin); print(d.get("content", json.dumps(d, indent=2)))
except Exception as e:
    sys.stdin.seek(0)' 2>/dev/null || cat
}

case "$cmd" in
  health)   get /health | python3 -m json.tool ;;
  profile)  post /profile "$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"description":a[0],**({"company_name":a[1]} if len(a)>1 else {}),**({"location":a[2]} if len(a)>2 else {})}))' "$@")" | show ;;
  search)   post /search "$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"keywords":a[0],**({"province":a[1]} if len(a)>1 else {}),"limit":8}))' "$@")" | show ;;
  brief)    post /brief    '{"days":14,"limit":5}' | show ;;
  matches)  post /matches  '{"days":60,"limit":8}' | show ;;
  deadlines)post /deadlines "{\"days\":${1:-30},\"limit\":15}" | show ;;
  details)  get "/details/$1" | show ;;
  analyze)  post /tools/refresh_data '{}' >/dev/null
            post /cohere/analyze "$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"reference":a[0],**({"question":a[1]} if len(a)>1 else {})}))' "$@")" | show ;;
  bidroom)  post /tools/refresh_data '{}' >/dev/null
            post /bid-room/process "$(python3 -c 'import json,sys; a=sys.argv[1:]; print(json.dumps({"reference":a[0],"max_attachments":3}))' "$@")" | show ;;
  cohere)   post /tools/check_cohere_status '{}' | show ;;
  *) grep '^#' "$0" | sed 's/^# \{0,1\}//' ; exit 0 ;;
esac
