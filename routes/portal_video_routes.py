# -*- coding: utf-8 -*-
"""routes/portal_video_routes.py — stranitsy portala dlya video-konspektov:
  • /portal/video — polnoekrannaya stranitsa so spiskom poslednikh obrabotok
  • /portal/widgets/videos?limit=N - HTML-vidzhet (fragment), mozhno vstraivat v drugie stranitsy or iframe

Mosty:
- Yavnyy: (UX v†" Memory) polzovatel Re Ester vidyat poslednie "epizody" videoanaliza v odnom meste.
- Skrytyy #1: (Logika v†" Navigatsiya) edinyy spisok daet bystrye tochki vkhoda k dampam/artefaktam.
- Skrytyy #2: (Inzheneriya v†" Ekspluatatsiya) vidzhet - bez pravki suschestvuyuschikh shablonov portala, drop-in-expansive.

Zemnoy abzats:
Eto “stand u operatorskoy”: na tablo visyat poslednie partii - otkuda prishli, kak raspilili, chto v sukhom ostatke.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ingest.video_reports import list_recent  # type: ignore
except Exception:
    def list_recent(limit: int = 20):
        return []

bp_portal_video = Blueprint("portal_video", __name__)

@bp_portal_video.route("/portal/video", methods=["GET"])
def portal_video_page():
    rows = list_recent(limit=50)
    return render_template("portal_video.html", rows=rows)

@bp_portal_video.route("/portal/widgets/videos", methods=["GET"])
def portal_video_widget():
    limit = 10
    try:
        limit = int(request.args.get("limit", "10"))
    except Exception:
        pass
    rows = list_recent(limit=limit)
    return render_template("widgets_video_recent.html", rows=rows)

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_portal_video)