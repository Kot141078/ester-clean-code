# -*- coding: utf-8 -*-
"""routes/metrics_video_extended.py - Prometheus-metriki dlya universal-videokonveyera.

Endpoint:
  • GET /metrics/video_ex

Export:
  - video_ex_cap_ffmpeg 0|1
  - video_ex_cap_ffprobe 0|1
  - video_ex_cap_ytdlp 0|1
  - video_ex_cap_whisper 0|1
  - video_ex_cap_fwhisper 0|1

Mosty:
- Yavnyy: (Nablyudaemost v†" Video) vidno, kakie rychagi dostupny.
- Skrytyy #1: (Kibernetika v†" Volya) mozhno vklyuchat A/B v RuleHub po faktu dostupnosti.
- Skrytyy #2: (Inzheneriya v†" Podderzhka) prostye binarnye schetchiki bez vneshnikh zavisimostey.

Zemnoy abzats:
Eto tablo “what iz instrumentov est pod rukoy” - prezhde chem zvat ekskavator.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_metrics_video_ex = Blueprint("metrics_video_ex", __name__)

try:
    from modules.video.metadata.ffprobe_ex import sys_capabilities  # type: ignore
except Exception:
    sys_capabilities = None  # type: ignore

def register(app):
    app.register_blueprint(bp_metrics_video_ex)

@bp_metrics_video_ex.route("/metrics/video_ex", methods=["GET"])
def metrics():
    if sys_capabilities is None:
        return Response("video_ex_cap_ffmpeg 0\nvideo_ex_cap_ffprobe 0\nvideo_ex_cap_ytdlp 0\nvideo_ex_cap_whisper 0\nvideo_ex_cap_fwhisper 0\n",
                        mimetype="text/plain; version=0.0.4; charset=utf-8")
    caps = sys_capabilities()
    lines = [
        f"video_ex_cap_ffmpeg {1 if caps.get('ffmpeg') else 0}",
        f"video_ex_cap_ffprobe {1 if caps.get('ffprobe') else 0}",
        f"video_ex_cap_ytdlp {1 if caps.get('yt_dlp') else 0}",
        f"video_ex_cap_whisper {1 if caps.get('python_whisper') else 0}",
        f"video_ex_cap_fwhisper {1 if caps.get('python_faster_whisper') else 0}",
    ]
# return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")