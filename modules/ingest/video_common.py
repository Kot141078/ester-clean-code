# -*- coding: utf-8 -*-
"""
modules/ingest/video_common.py — nizkourovnevye utility dlya video/audio konveyera (ffprobe/ffmpeg, chanking, bezopasnyy zapusk).

Mosty:
- Yavnyy: (Infoteoriya → Kibernetika) Ogranichenie slozhnykh potokov do unifitsirovannykh blokov (chanki audio) ⇢ upravlyaemost payplayna (Ashbi).
- Skrytyy #1: (Bayes ↔ Memory) Proba i metadannye — apriori dlya posleduyuschey interpretatsii ASR; rezultaty zapisyvayutsya v StructuredMemory (pri nalichii).
- Skrytyy #2: (Logika ↔ Inzheneriya PO) Determinirovannyy split + idempotent zapis faylov ⇢ proveryaemost/povtoryaemost.

Zemnoy abzats:
Eto «tokarnyy stanok» dlya media: ffprobe — shtangentsirkul (izmeryaem parametry), ffmpeg — rezets (narezaem zagotovku na ravnye plashki zvuka), dalee ikh mozhno obrabatyvat parallelno i nadezhno skladyvat.

# c=a+b
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkie importy «yadra» ingest (drop-in, bez zhestkikh svyazey)
try:
    from modules.ingest.common import persist_dir, save_bytes  # type: ignore
except Exception:
    def persist_dir() -> str:
        root = os.path.abspath(os.path.join(os.getcwd(), "data"))
        os.makedirs(root, exist_ok=True)
        return root
    def save_bytes(path: str, data: bytes) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

@dataclass
class ProbeResult:
    ok: bool
    raw: Dict[str, object]
    duration: float
    streams: List[Dict[str, object]]
    format_name: str
    error: Optional[str] = None

def _safe_run(cmd: List[str], timeout: float = 120.0) -> Tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=timeout)
    return proc.returncode, out, err

def ffprobe(path: str) -> ProbeResult:
    """
    Vozvraschaet ProbeResult po lokalnomu puti.
    Trebuet ffprobe v PATH. Esli net — ok=False, error.
    """
    if not os.path.isfile(path):
        return ProbeResult(False, {}, 0.0, [], "", error=f"file-not-found: {path}")
    code, out, err = _safe_run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], timeout=60.0)
    if code != 0:
        return ProbeResult(False, {}, 0.0, [], "", error=err.strip())
    try:
        data = json.loads(out)
    except Exception as e:
        return ProbeResult(False, {}, 0.0, [], "", error=f"bad-json: {e}")
    fmt = data.get("format", {}) or {}
    dur = float(fmt.get("duration") or 0.0)
    streams = list(data.get("streams") or [])
    return ProbeResult(True, data, dur, streams, str(fmt.get("format_name") or ""))

def extract_subs_ffmpeg(path: str, out_dir: str) -> List[str]:
    """
    Pytaetsya vytaschit vstroennye subtitry (esli est) v SRT.
    Vozvraschaet spisok putey srt, mozhet byt pustym.
    """
    pr = ffprobe(path)
    if not pr.ok:
        return []
    subs: List[str] = []
    idx = 0
    for i, s in enumerate(pr.streams):
        if str(s.get("codec_type")) == "subtitle":
            out_srt = os.path.join(out_dir, f"subs_{idx:02d}.srt")
            code, _, _ = _safe_run(["ffmpeg", "-y", "-i", path, "-map", f"0:s:{i - _first_index(pr.streams, 'subtitle')}", out_srt], timeout=21600.0)
            if code == 0 and os.path.isfile(out_srt):
                subs.append(out_srt)
                idx += 1
    return subs

def _first_index(streams: List[Dict[str, object]], codec_type: str) -> int:
    for i, s in enumerate(streams):
        if str(s.get("codec_type")) == codec_type:
            return i
    return 0

def audio_to_wav(path: str, out_wav: str, sr: int = 16000, mono: bool = True) -> str:
    """
    Izvlekaet audio v WAV (16kHz mono po umolchaniyu) — optimalno dlya ASR/Whisper.
    """
    args = ["ffmpeg", "-y", "-i", path, "-ar", str(sr)]
    if mono:
        args += ["-ac", "1"]
    args += [out_wav]
    code, _, err = _safe_run(args, timeout=21600.0)
    if code != 0:
        raise RuntimeError(f"ffmpeg failed: {err.strip()}")
    return out_wav

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def chunk_wav(path: str, out_dir: str, chunk_ms: int = 5 * 60 * 1000, overlap_ms: int = 5 * 1000) -> List[Tuple[str, float, float]]:
    """
    Rezhet WAV na kuski so sdvigom (overlap) dlya ustoychivosti ASR.
    Vozvraschaet spisok (chunk_path, start_sec, end_sec).
    """
    # Poluchim dlitelnost cherez ffprobe
    pr = ffprobe(path)
    if not pr.ok:
        # zapasnoy sposob — cherez sox/ffprobe uzhe upal
        raise RuntimeError(f"ffprobe failed for wav: {pr.error}")

    duration = pr.duration or 0.0
    chunk_sec = chunk_ms / 1000.0
    overlap = overlap_ms / 1000.0
    if duration <= 0.0:
        # Na vsyakiy sluchay narezhem 1 kusok
        dst = os.path.join(out_dir, "chunk_000.wav")
        shutil.copyfile(path, dst)
        return [(dst, 0.0, 0.0)]

    out: List[Tuple[str, float, float]] = []
    t = 0.0
    idx = 0
    while t < duration:
        start = max(0.0, t - (overlap if idx > 0 else 0.0))
        end = min(duration, t + chunk_sec)
        dst = os.path.join(out_dir, f"chunk_{idx:03d}.wav")
        # ffmpeg -ss start -t (end-start)
        leng = max(0.1, end - start)
        code, _, err = _safe_run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{leng:.3f}", "-i", path, dst], timeout=180.0)
        if code != 0:
            raise RuntimeError(f"ffmpeg split failed: {err.strip()}")
        out.append((dst, start, end))
        idx += 1
        t += chunk_sec
    return out

def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
# return path




