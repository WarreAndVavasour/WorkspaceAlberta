#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   export QWEN_TTS_BASE_URL="https://<your-space>.hf.space"
#   export HF_TOKEN="hf_xxx"   # optional for private endpoint
#   ./scripts/voice/smoke_test_qwen_hf.sh /path/to/ref.wav "Short transcript"

REF_AUDIO="${1:-}"
REF_TEXT="${2:-}"

if [[ -z "${QWEN_TTS_BASE_URL:-}" ]]; then
  echo "QWEN_TTS_BASE_URL is required"
  exit 1
fi
if [[ -z "$REF_AUDIO" ]]; then
  echo "Reference audio path is required as arg1"
  exit 1
fi

python3 scripts/voice/hf_qwen_client.py \
  --base-url "$QWEN_TTS_BASE_URL" \
  --token "${HF_TOKEN:-}" \
  --mode voice_clone \
  --text "Hello from OpenClaw. This is a smoke test for Qwen voice cloning." \
  --language English \
  --ref-audio "$REF_AUDIO" \
  --ref-text "$REF_TEXT" \
  --out ./tmp/qwen_smoke.wav

echo "Smoke test output: ./tmp/qwen_smoke.wav"
