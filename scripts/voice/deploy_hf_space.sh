#!/usr/bin/env bash
set -euo pipefail

# Deploy Qwen voice server to a Hugging Face Docker Space via git push.
# Required env:
#   HF_TOKEN=hf_xxx
#   HF_SPACE_ID=username/space-name
# Optional env:
#   HF_SPACE_VISIBILITY=private|public (default: private)

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "ERROR: HF_TOKEN is not set"
  exit 1
fi
if [[ -z "${HF_SPACE_ID:-}" ]]; then
  echo "ERROR: HF_SPACE_ID is not set (example: HarleyCoops/alberta-voice-qwen)"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VOICE_DIR="$ROOT_DIR/scripts/voice"
TMP_DIR="$(mktemp -d /tmp/hf-space-qwen-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

cp "$VOICE_DIR/hf_space_qwen_server.py" "$TMP_DIR/app.py"
cp "$VOICE_DIR/requirements-space-qwen.txt" "$TMP_DIR/requirements.txt"

cat > "$TMP_DIR/Dockerfile" <<'EOF'
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
ENV PORT=7860
EXPOSE 7860
CMD ["python3", "/app/app.py"]
EOF

cat > "$TMP_DIR/README.md" <<'EOF'
---
title: Alberta Qwen Voice Server
emoji: 🗣️
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: false
license: apache-2.0
---

Qwen3-TTS voice server for OpenClaw.

Endpoints:
- GET /health
- POST /synthesize
EOF

pushd "$TMP_DIR" >/dev/null
  git init
  git checkout -b main
  git add .
  git -c user.name='openclaw' -c user.email='openclaw@local' commit -m 'Initial HF Space deploy for Qwen voice server'

  REMOTE_URL="https://user:${HF_TOKEN}@huggingface.co/spaces/${HF_SPACE_ID}"
  git remote add origin "$REMOTE_URL"
  git push -u origin main --force
popd >/dev/null

echo "Deployed to https://huggingface.co/spaces/${HF_SPACE_ID}"
echo "Next: set Space hardware to L4/A10G and optionally set secrets/env vars:"
echo "  QWEN_CUSTOM_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
echo "  QWEN_BASE_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base"
echo "  QWEN_DTYPE=bfloat16"
