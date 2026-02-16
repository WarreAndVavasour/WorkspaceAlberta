# Voice Cloning + TTS on Hugging Face for OpenClaw (Qwen3-TTS)

## TL;DR
- **`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` is *not* user voice cloning**. It provides 9 built-in premium speakers + instruction/style control.
- For **actual custom speaker cloning**, use **`Qwen/Qwen3-TTS-12Hz-1.7B-Base`** (or `0.6B-Base`) with `ref_audio` + `ref_text`.
- Best practical setup for OpenClaw: deploy a **private HF Space or Inference Endpoint** running a small FastAPI wrapper, then call it from local scripts.

---

## 1) Model capability check (what works / what doesn’t)

## Target model in request
`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`

What it supports:
- text-to-speech
- style/instruction control (`instruct`)
- fixed built-in speaker set (e.g., Ryan, Vivian, etc.)

What it does **not** support:
- arbitrary user voice cloning from your own reference audio

For user voice cloning use:
- `Qwen/Qwen3-TTS-12Hz-1.7B-Base` (higher quality, heavier)
- `Qwen/Qwen3-TTS-12Hz-0.6B-Base` (lighter, cheaper/faster)

Reference requirements (from Qwen docs/API behavior):
- `ref_audio`: local path / URL / base64 / waveform tuple
- `ref_text`: transcript of the reference clip (recommended for quality)
- `x_vector_only_mode=True` allows clone with no transcript, but quality can drop
- Qwen advertises **3-second rapid voice clone** capability (longer clean refs usually improve stability)

Practical reference audio guidance:
- 3–15s clean speech clip (single speaker)
- WAV preferred (16kHz–48kHz, mono)
- minimal background noise/reverb/music
- accurate transcript for best timbre/prosody transfer

---

## 2) Licensing and compliance

Model metadata indicates:
- License: **Apache-2.0**
- Public, not gated (at time of writing)

Still required:
- obtain permission to clone a voice
- follow local legal/privacy/biometric/consent requirements
- disclose synthetic audio where policy/law requires

---

## 3) Compute + cost expectations

### Hardware expectations (practical)
- `1.7B` models: target **24GB+ VRAM** (A10G/L4 class), BF16/FP16, FlashAttention2 preferred
- `0.6B` models: can fit smaller GPUs (often easier on 16GB+)
- CPU-only is generally impractical for low-latency production

### HF published price points (reference)
From HF pricing page (subject to change):
- Spaces: T4 ~$0.40/h, L4 ~$0.80/h, A10G ~$1.00/h, A100 ~$2.50/h
- Inference Endpoints GPU: similar class pricing (A10G ~$1.00/h)

Rule of thumb:
- **dev/test**: Space on L4 or A10G
- **prod**: Inference Endpoint (private networking, autoscaling, SLA patterns)

Latency notes:
- first request after cold start/model load is much slower (can be 30–120s)
- warm inference for short utterances often a few seconds on L4/A10G (depends on text length + queue)

---

## 4) Deployment path on Hugging Face (recommended)

## Option A (recommended first): Private HF Space + FastAPI wrapper

Why:
- easiest to iterate/debug
- simple HTTP contract for OpenClaw integration

### A1. Create Space
1. Hugging Face → **New Space**
2. SDK: **Docker** (or Gradio; Docker gives full control)
3. Visibility: **Private**
4. Hardware: start with **1x L4** or **A10G**

### A2. Upload server files
Use file in this workspace:
- `scripts/voice/hf_space_qwen_server.py`
- `scripts/voice/requirements-space-qwen.txt`

Set Space startup command to run uvicorn, e.g.:
```bash
python hf_space_qwen_server.py
```

### A3. Set Space secrets / variables
Use HF Space settings (do not commit secrets):
- (optional) `HF_TOKEN` if required for gated/private pulls
- optional model overrides:
  - `QWEN_CUSTOM_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`
  - `QWEN_BASE_MODEL_ID=Qwen/Qwen3-TTS-12Hz-1.7B-Base`
  - `QWEN_DTYPE=bfloat16`

### A4. Verify
```bash
curl -s https://<your-space>.hf.space/health
```

### A5. Inference from local machine
Use client script in this workspace:
- `scripts/voice/hf_qwen_client.py`

Voice clone call:
```bash
python3 scripts/voice/hf_qwen_client.py \
  --base-url https://<your-space>.hf.space \
  --token "$HF_TOKEN" \
  --mode voice_clone \
  --text "This is a cloned voice test from OpenClaw." \
  --language English \
  --ref-audio ./ref.wav \
  --ref-text "This is the transcript of the reference clip." \
  --out ./tmp/out_qwen_clone.wav
```

CustomVoice call (non-cloned built-in speaker):
```bash
python3 scripts/voice/hf_qwen_client.py \
  --base-url https://<your-space>.hf.space \
  --token "$HF_TOKEN" \
  --mode custom_voice \
  --speaker Ryan \
  --instruct "Calm, warm tone" \
  --text "Hello from OpenClaw." \
  --language English \
  --out ./tmp/out_qwen_custom.wav
```

---

## Option B: Inference Endpoint

Use when you need production controls (autoscaling, stable endpoint ops).

Steps:
1. Create custom Endpoint (GPU L4/A10G recommended)
2. Deploy container or custom handler equivalent to `hf_space_qwen_server.py`
3. Restrict with token/private networking
4. Point `hf_qwen_client.py --base-url` to endpoint URL

If endpoint containerization overhead is high, start with Space and migrate once API contract is stable.

---

## 5) Local scripts included in this workspace

- `scripts/voice/hf_space_qwen_server.py`
  - server to host on HF Space/Endpoint
- `scripts/voice/hf_qwen_client.py`
  - local CLI client for synth requests
- `scripts/voice/smoke_test_qwen_hf.sh`
  - quick end-to-end test wrapper
- `scripts/voice/xtts_fallback_local.py`
  - fallback local voice cloning using Coqui XTTS v2

Dependency files:
- `scripts/voice/requirements-space-qwen.txt`
- `scripts/voice/requirements-qwen-client.txt`
- `scripts/voice/requirements-xtts-fallback.txt`

---

## 6) Quick smoke test

```bash
python3 -m venv .venv-voice
source .venv-voice/bin/activate
pip install -r scripts/voice/requirements-qwen-client.txt

export QWEN_TTS_BASE_URL="https://<your-space>.hf.space"
export HF_TOKEN="hf_..."   # if needed

./scripts/voice/smoke_test_qwen_hf.sh ./ref.wav "Transcript of the ref clip"
```

Expected output:
- `./tmp/qwen_smoke.wav`

---

## 7) Fallback path (if Qwen deployment is not feasible)

Recommended fallback: **Coqui XTTS v2** (open-source, multilingual, good cloning quality).

Install fallback deps:
```bash
pip install -r scripts/voice/requirements-xtts-fallback.txt
```

Run:
```bash
python3 scripts/voice/xtts_fallback_local.py \
  --text "Fallback synthesis test" \
  --ref-audio ./ref.wav \
  --language en \
  --out ./tmp/out_xtts.wav
```

When to switch to fallback:
- Qwen GPU footprint/cost too high
- model load/cold-start too slow for your SLA
- environment incompatibility (FlashAttention/CUDA stack)

---

## 8) OpenClaw integration notes

In OpenClaw flows, call the local client script from shell tasks, then pass resulting WAV to messaging/TTS handoff logic.

Example shell step:
```bash
python3 scripts/voice/hf_qwen_client.py \
  --base-url "$QWEN_TTS_BASE_URL" \
  --mode voice_clone \
  --text "Your requested update is ready." \
  --language English \
  --ref-audio ./voice_refs/christian_ref.wav \
  --ref-text "Reference transcript here" \
  --out ./tmp/reply.wav
```

Security:
- keep tokens in env vars only (`HF_TOKEN`)
- do not commit secrets to workspace files
- keep Space private if handling personal voice data
- avoid storing reference voice files longer than needed

---

## 9) Troubleshooting

- **OOM / CUDA out of memory**
  - move from 1.7B → 0.6B
  - use larger GPU (L4/A10G+)
  - ensure BF16/FP16 + FlashAttention2

- **Very long first request latency**
  - model cold start; keep instance warm
  - reduce scale-to-zero aggressiveness

- **Clone quality poor**
  - provide clean 5–15s reference clip
  - provide accurate `ref_text`
  - avoid noisy/multi-speaker references

- **Space 5xx errors**
  - inspect Space logs for dependency mismatches
  - pin versions from requirements files

- **No auth / 401**
  - verify `HF_TOKEN`
  - confirm endpoint visibility/token scope

---

## 10) Practical recommendation for this setup

1. Keep `CustomVoice` for controlled preset voices.
2. Deploy `1.7B-Base` for actual cloning via private Space first.
3. If cost/latency is high, downgrade cloning backend to `0.6B-Base`.
4. Maintain XTTS fallback for resilience.
