# -*- coding: utf-8 -*-
"""
routes/video_sources_capmap.py — karta sposobnostey istochnikov/binarey/lokalnykh formatov.

Endpoint:
  • GET /ingest/video/sources/capmap

Mosty:
- Yavnyy: (UX v†" Video) operator srazu vidit, kakie istochniki realno podderzhany.
- Skrytyy #1: (Infoteoriya v†" Planirovanie) mozhno vklyuchat A/B ili otklyuchat tyazhelye vetki.
- Skrytyy #2: (Kibernetika v†" Volya) pravila myshleniya korrektiruyut povedenie po capmap.

Zemnoy abzats:
Eto kak nakleyki na pulte: «est ffmpeg/yt-dlp, MKV ok, ISO chastichno».

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_video_capmap = Blueprint("video_capmap", __name__)

try:
    from modules.video.metadata.ffprobe_ex import sys_capabilities  # type: ignore
except Exception:
    sys_capabilities = None  # type: ignore

def register(app):
    app.register_blueprint(bp_video_capmap)

@bp_video_capmap.route("/ingest/video/sources/capmap", methods=["GET"])
def capmap():
    caps = sys_capabilities() if sys_capabilities else {}
    m = {
        "ok": True,
        "binaries": {
            "ffprobe": bool(caps.get("ffprobe")),
            "ffmpeg": bool(caps.get("ffmpeg")),
            "yt_dlp": bool(caps.get("yt_dlp")),
            "whisper": bool(caps.get("python_whisper")),
            "faster_whisper": bool(caps.get("python_faster_whisper")),
        },
        "providers": {
            "youtube": bool(caps.get("yt_dlp")),
            "vimeo": bool(caps.get("yt_dlp")),
            "rutube": bool(caps.get("yt_dlp")),
            "generic": bool(caps.get("yt_dlp")),
        },
        "local_formats": {
            "mkv": True,
            "mp4": True,
            "mov": True,
            "avi": True,
            "m3u8": True,
            "dvd_iso_folder": True,  # best-effort
        },
        "env": {
            "SUBS_SIDECAR_GLOB": os.getenv("SUBS_SIDECAR_GLOB", "1"),
            "MKV_EXTRACT_LANG_PREF": os.getenv("MKV_EXTRACT_LANG_PREF", "ru,en"),
        }
    }
    return jsonify(m)
