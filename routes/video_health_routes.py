# -*- coding: utf-8 -*-
"""
routes/video_health_routes.py — health/selfcheck endpoint dlya video-konveyera.

Endpoint:
  - GET /health/video/selfcheck — vozvraschaet JSON-otchet proverok (binari, moduli, ENV, direktorii).

Mosty:
- Yavnyy: (Nablyudaemost v†" Ekspluatatsiya) podnyali v HTTP to, chto ranshe bylo tolko CLI — teper vidno «zdorove» uzla.
- Skrytyy #1: (Kibernetika v†" R egulyatsiya) mozhno triggerit alerty po otsutstviyu binarey/modeley.
- Skrytyy #2: (Inzheneriya v†" Nadezhnost) proverka ne menyaet sostoyanie — «chtenie bez pobochek».

Zemnoy abzats:
Eto «kontrolnaya lampa» na paneli: zelenaya — vse okey, krasnaya — zovi mastera.

# c=a+b
"""
from __future__ import annotations

import json
import os
import shutil

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_video_health = Blueprint("video_health", __name__)

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _py(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False

@bp_video_health.route("/health/video/selfcheck", methods=["GET"])
def health_selfcheck():
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
        "ok": True
    }
    # prostye podskazki
    advice = []
    if not rep["bins"]["ffmpeg"] or not rep["bins"]["ffprobe"]:
        advice.append("Ustanovi ffmpeg/ffprobe i dobav v PATH.")
    if not rep["bins"]["yt-dlp"]:
        advice.append("Ustanovi yt-dlp (pip install yt-dlp) i dobav v PATH.")
    if env.get("VIDEO_INGEST_AB", "A").upper() == "B" and not rep["py"]["faster_whisper"]:
        advice.append("A/B=B vybran, no faster-whisper ne nayden. Libo verni A, libo ustanovi faster-whisper.")
    if advice:
        rep["advice"] = advice
    return jsonify(rep)

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_video_health)