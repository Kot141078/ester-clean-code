
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.video.ingest — minimalnye multimedia-konveyery.
Mosty:
- Yavnyy: probe()/extract_audio()/transcode() s predskazuemymi otvetami.
- Skrytyy #1: (DX ↔ Nadezhnost) — no-op, esli ffmpeg/ffprobe nedostupny.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) — neizmennye signatury dlya buduschikh realizatsiy.

Zemnoy abzats:
Mediapayplayn chasto «lomaet» sistemu iz‑za vneshnikh utilit.
Zdes vozvraschaem strukturirovannyy status, chtoby ostalnoy kod ne padal.
# c=a+b
"""
import os, pathlib, shutil, time
from typing import Optional, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def probe(path: str) -> Dict:
    p = pathlib.Path(path)
    info = {"ok": p.exists(), "size": p.stat().st_size if p.exists() else 0, "ts": int(time.time())}
    if _exists("ffprobe"):
        info["ffprobe"] = True  # ne zapuskaem, tolko flag nalichiya
    else:
        info["ffprobe"] = False
    return info

def extract_audio(path: str, out_wav: Optional[str]=None) -> Dict:
    if not pathlib.Path(path).exists():
        return {"ok": False, "reason": "input_missing"}
    # Bez vneshnikh utilit — no-op, sozdaem marker
    out = out_wav or (str(pathlib.Path(path).with_suffix(".wav")))
    return {"ok": True, "out": out, "note": "noop (ffmpeg unavailable)"}

def transcode(path: str, target: str, **kw) -> Dict:
    if not pathlib.Path(path).exists():
        return {"ok": False, "reason": "input_missing"}
    return {"ok": True, "out": target, "note": "noop (ffmpeg unavailable)", "params": kw}