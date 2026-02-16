#!/usr/bin/env python3
"""Client for Qwen3-TTS HF Space/Endpoint server (/synthesize)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests


def parse_args():
    p = argparse.ArgumentParser(description="Call hosted Qwen3-TTS server")
    p.add_argument("--base-url", default=os.getenv("QWEN_TTS_BASE_URL", ""), help="https://<space>.hf.space or endpoint URL")
    p.add_argument("--token", default=os.getenv("HF_TOKEN", ""), help="HF token if endpoint is protected")
    p.add_argument("--mode", choices=["custom_voice", "voice_clone"], default="voice_clone")
    p.add_argument("--text", required=True)
    p.add_argument("--language", default="Auto")
    p.add_argument("--speaker", default="Ryan", help="Used by custom_voice")
    p.add_argument("--instruct", default="", help="Style instruction")
    p.add_argument("--ref-audio", default="", help="Path to reference wav/mp3 for voice_clone")
    p.add_argument("--ref-text", default="", help="Transcript for reference audio (recommended)")
    p.add_argument("--out", default="./out.wav")
    return p.parse_args()


def main():
    args = parse_args()
    if not args.base_url:
        raise SystemExit("ERROR: set --base-url or QWEN_TTS_BASE_URL")

    url = args.base_url.rstrip("/") + "/synthesize"
    headers = {}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"

    data = {
        "mode": args.mode,
        "text": args.text,
        "language": args.language,
        "speaker": args.speaker,
        "instruct": args.instruct,
        "ref_text": args.ref_text,
    }

    files = None
    if args.mode == "voice_clone":
        if not args.ref_audio:
            raise SystemExit("ERROR: --ref-audio is required for voice_clone mode")
        ref_path = Path(args.ref_audio)
        if not ref_path.exists():
            raise SystemExit(f"ERROR: file not found: {ref_path}")
        files = {"ref_audio": (ref_path.name, ref_path.open("rb"), "audio/wav")}

    resp = requests.post(url, data=data, files=files, headers=headers, timeout=600)
    if resp.status_code != 200:
        print(resp.text)
        raise SystemExit(f"ERROR: request failed ({resp.status_code})")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    print(f"Saved: {out_path.resolve()}")


if __name__ == "__main__":
    main()
