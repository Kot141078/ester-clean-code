# -*- coding: utf-8 -*-
"""
Deterministic offline ASR baseline.

No external model is required. The engine validates WAV input and produces a
stable transcript placeholder with audio metadata so downstream pipelines can
work predictably in closed-box environments.
"""
from __future__ import annotations

import io
import os
import time
import wave
from typing import Any, Dict, Iterable, Optional

from modules.ingest.common import persist_dir


def _safe_stem(name: str) -> str:
    base = os.path.basename(str(name or "audio"))
    stem, _ext = os.path.splitext(base)
    stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)
    return stem or "audio"


def _looks_like_wav(name: str, data: bytes) -> bool:
    low = str(name or "").lower()
    if low.endswith(".wav"):
        return True
    return bool(data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE")


def _wav_meta(data: bytes) -> Dict[str, Any]:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            channels = int(w.getnchannels() or 0)
            rate = int(w.getframerate() or 0)
            nframes = int(w.getnframes() or 0)
            sampwidth = int(w.getsampwidth() or 0)
            duration = (float(nframes) / float(rate)) if rate > 0 else 0.0
            return {
                "channels": channels,
                "sample_rate": rate,
                "frames": nframes,
                "sample_width": sampwidth,
                "duration_sec": duration,
            }
    except Exception as e:
        raise RuntimeError("ACP only supports VAV: corrupted VAV stream") from e


def _load_bytes(name: str, data: Optional[bytes]) -> bytes:
    if data is not None:
        return bytes(data)
    path = str(name or "").strip()
    if not path or not os.path.isfile(path):
        raise RuntimeError("ASR ozhidaet WAV-dannye ili put k WAV-faylu")
    with open(path, "rb") as f:
        return f.read()


def asr_transcribe(
    name: str,
    data: Optional[bytes] = None,
    lang: str = "ru",
    tags: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    raw = _load_bytes(name, data)
    if not _looks_like_wav(name, raw):
        raise RuntimeError("ACP only supports VAV")

    meta = _wav_meta(raw)
    root = os.path.join(persist_dir(), "ingest", "asr")
    os.makedirs(root, exist_ok=True)
    ts = int(time.time())
    out_path = os.path.join(root, f"{_safe_stem(name)}_{ts}.txt")

    # Deterministic offline transcript placeholder with useful metadata.
    duration = float(meta.get("duration_sec") or 0.0)
    text = f"[offline-asr:{lang}] duration={duration:.2f}s"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    return {
        "ok": True,
        "text": text,
        "path": out_path,
        "mime": "audio/wav",
        "engine": "offline-wav-baseline",
        "segments": [{"start": 0.0, "end": duration, "text": text}] if duration > 0 else [],
        "meta": meta,
        "tags": list(tags or []),
    }
