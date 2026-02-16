#!/usr/bin/env python3
"""
Fallback high-quality voice cloning with Coqui XTTS v2.
Requires: pip install TTS>=0.22.0 soundfile
GPU strongly recommended.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Fallback voice cloning via XTTS v2")
    p.add_argument("--text", required=True)
    p.add_argument("--ref-audio", required=True, help="Reference speaker wav/mp3")
    p.add_argument("--language", default="en")
    p.add_argument("--out", default="./out_xtts.wav")
    p.add_argument("--model", default="tts_models/multilingual/multi-dataset/xtts_v2")
    return p.parse_args()


def main():
    args = parse_args()
    from TTS.api import TTS  # lazy import

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    tts = TTS(args.model)
    tts.tts_to_file(
        text=args.text,
        speaker_wav=args.ref_audio,
        language=args.language,
        file_path=str(out),
    )
    print(f"Saved: {out.resolve()}")


if __name__ == "__main__":
    main()
