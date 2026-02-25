# -*- coding: utf-8 -*-
"""routes/metrics_video_routes.py - Prometheus-metriki video-konveyera.
  • /metrics/video - tekst v format Prometheus exposition.

Export:
  - video_ingest_success_total{backend="..."} <count>
  - video_summary_chars_total <count>
  - video_transcript_chars_total <count>
  - video_latest_timestamp_seconds <unix>

Mosty:
- Yavnyy: (Nablyudaemost v†" Ekspluatatsiya) metrics dlya alertov/dosok bez troganiya obschego/metrics.
- Skrytyy #1: (Kibernetika v†" R egulyatsiya) po schetchikam legko otsenit propusknuyu sposobnost Re izderzhki ASR.
- Skrytyy #2: (Infoteoriya v†" Kachestvo) obem tekstov - proksi kachestva izvlecheniya (slishkom malo/mnogo v†' signaly).

Zemnoy abzats:
This is “schetchik u prokhodnoy”: skolko yaschikov proshlo, kakogo tipa stanok rabotal, kogda posledniy raz konveyer shevelilsya.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ingest.video_reports import compute_metrics  # type: ignore
except Exception:
    def compute_metrics():
        return {"success_by_backend": {}, "summary_chars_total": 0, "transcript_chars_total": 0, "latest_ts": 0}

bp_metrics_video = Blueprint("metrics_video", __name__)

@bp_metrics_video.route("/metrics/video", methods=["GET"])
def metrics_video():
    m = compute_metrics()
    lines = []
    # success counters
    for backend, cnt in (m.get("success_by_backend") or {}).items():
        # ekraniruem kavychki v label
        b = str(backend).replace('"', '\\"')
        lines.append(f'video_ingest_success_total{{backend="{b}"}} {int(cnt)}')
    # totals
    lines.append(f'video_summary_chars_total {int(m.get("summary_chars_total", 0))}')
    lines.append(f'video_transcript_chars_total {int(m.get("transcript_chars_total", 0))}')
    lines.append(f'video_latest_timestamp_seconds {int(m.get("latest_ts", 0))}')
    body = "\n".join(lines) + "\n"
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_metrics_video)