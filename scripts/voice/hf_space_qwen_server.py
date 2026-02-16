#!/usr/bin/env python3
"""
Minimal FastAPI server for Hugging Face Space/Endpoint that exposes:
- GET /health
- POST /synthesize (multipart)

Modes:
- custom_voice: uses Qwen3-TTS-12Hz-1.7B-CustomVoice (preset speakers)
- voice_clone: uses Qwen3-TTS-12Hz-1.7B-Base with ref_audio + ref_text
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from qwen_tts import Qwen3TTSModel

CUSTOM_MODEL_ID = os.getenv("QWEN_CUSTOM_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
BASE_MODEL_ID = os.getenv("QWEN_BASE_MODEL_ID", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
DTYPE = os.getenv("QWEN_DTYPE", "bfloat16")
ATTN_IMPL = os.getenv("QWEN_ATTN_IMPL", "flash_attention_2")


def resolve_dtype(dtype_name: str):
    if dtype_name.lower() in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if dtype_name.lower() in {"fp16", "float16"}:
        return torch.float16
    return torch.float32


def load_model(model_id: str) -> Qwen3TTSModel:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for practical Qwen3-TTS inference.")
    return Qwen3TTSModel.from_pretrained(
        model_id,
        device_map="cuda:0",
        dtype=resolve_dtype(DTYPE),
        attn_implementation=ATTN_IMPL,
    )


app = FastAPI(title="Qwen3-TTS Server", version="0.1.0")
_custom_model: Optional[Qwen3TTSModel] = None
_base_model: Optional[Qwen3TTSModel] = None


@app.get("/health")
def health():
    return {
        "ok": True,
        "cuda": torch.cuda.is_available(),
        "custom_model": CUSTOM_MODEL_ID,
        "base_model": BASE_MODEL_ID,
    }


@app.post("/synthesize")
async def synthesize(
    mode: str = Form("custom_voice"),
    text: str = Form(...),
    language: str = Form("Auto"),
    speaker: str = Form("Ryan"),
    instruct: str = Form(""),
    ref_text: str = Form(""),
    ref_audio: Optional[UploadFile] = File(default=None),
):
    global _custom_model, _base_model

    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    try:
        if mode == "custom_voice":
            if _custom_model is None:
                _custom_model = load_model(CUSTOM_MODEL_ID)
            wavs, sr = _custom_model.generate_custom_voice(
                text=text,
                language=language,
                speaker=speaker,
                instruct=instruct,
            )
        elif mode == "voice_clone":
            if ref_audio is None:
                raise HTTPException(status_code=400, detail="ref_audio is required for voice_clone")
            if _base_model is None:
                _base_model = load_model(BASE_MODEL_ID)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                raw = await ref_audio.read()
                tmp.write(raw)
                tmp_path = tmp.name

            wavs, sr = _base_model.generate_voice_clone(
                text=text,
                language=language,
                ref_audio=tmp_path,
                ref_text=ref_text if ref_text.strip() else None,
                x_vector_only_mode=not bool(ref_text.strip()),
            )
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        else:
            raise HTTPException(status_code=400, detail="mode must be custom_voice or voice_clone")

        out_dir = tempfile.mkdtemp(prefix="qwen3tts_")
        out_path = os.path.join(out_dir, "output.wav")
        wav = np.asarray(wavs[0])
        sf.write(out_path, wav, sr)
        return FileResponse(out_path, media_type="audio/wav", filename="output.wav")

    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("hf_space_qwen_server:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")), reload=False)
