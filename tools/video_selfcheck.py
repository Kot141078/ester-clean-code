#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/video_selfcheck.py - oflayn-proverka okruzheniya dlya video-konveyera.

What to prove:
  • Nalichie binarey: ffmpeg, ffprobe, yt-dlp.
  • Nalichie Python-modules: faster-whisper (dlya B-slot), (optsionalno) modules.ingest.asr_engine (A-slot).
  • ENV-presety: VIDEO_INGEST_AB, VIDEO_ASR_MODEL, VIDEO_SUBS_ENABLED, USE_CUDA.
  • Direktorii: data/video_ingest.

Vykhod: JSON-otchet dlya udobstva v logakh/CI.

Mosty:
- Yavnyy: (Inzheneriya ↔ Ekspluatatsiya) “diagnostik” pered startom - menshe syurprizov v rantayme.
- Skrytyy #1: (Kibernetika ↔ Regulyatsiya) cherez ENV mozhno bystro pereklyuchat A/B i resursy (CPU/GPU).
- Skrytyy #2: (Infoteoriya ↔ Nadezhnost) odnotipnyy format otcheta uproschaet analiz/alerty.

Zemnoy abzats:
This is how predsmennyy cheklist stanka: smazka est, pitanie podano, reztsy na meste - zapuskaem.

# c=a+b"""
from __future__ import annotations

import json
import os
import shutil
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _py(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False

def main(argv=None) -> int:
    env = {
        "VIDEO_INGEST_AB": os.getenv("VIDEO_INGEST_AB", "A"),
        "VIDEO_ASR_MODEL": os.getenv("VIDEO_ASR_MODEL", "medium"),
        "VIDEO_SUBS_ENABLED": os.getenv("VIDEO_SUBS_ENABLED", "0"),
        "USE_CUDA": os.getenv("USE_CUDA", "")
    }
    rep = {
        "bins": {
            "ffmpeg": _have("ffmpeg"),
            "ffprobe": _have("ffprobe"),
            "yt-dlp": _have("yt-dlp")
        },
        "py": {
            "faster_whisper": _py("faster_whisper"),
            "asr_engine": _py("modules.ingest.asr_engine")
        },
        "env": env,
        "paths": {
            "data_video_ingest": os.path.isdir(os.path.join("data", "video_ingest"))
        },
        "advice": []
    }
    if not rep["bins"]["ffmpeg"] or not rep["bins"]["ffprobe"]:
        rep["advice"].append("Ustanovi ffmpeg/ffprobe i dobav v PATH.")
    if not rep["bins"]["yt-dlp"]:
        rep["advice"].append("Ustanovi yt-dlp (pip install yt-dlp) i dobav v PATH.")
    if env.get("VIDEO_INGEST_AB", "A").upper() == "B" and not rep["py"]["faster_whisper"]:
        rep["advice"].append("A/B=B vybran, no faster-whisper ne nayden. Vklyuchi A, ili ustanovi faster-whisper.")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
