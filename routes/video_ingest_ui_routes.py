# -*- coding: utf-8 -*-
"""
routes/video_ingest_ui_routes.py — prostaya admin-stranitsa /admin/video: ruchnoy zapusk analiza video.

Mosty:
- Yavnyy: (UX v†" Konveyer) Zivoy pult nad REST: vvod, knopka, rezultat — bez obkhodnykh putey.
- Skrytyy #1: (Logika v†" Memory) Polzovatel vidit JSON Re put dampa, mozhet sopostavit s kartochkami pamyati.
- Skrytyy #2: (Inzheneriya v†" Ekspluatatsiya) JS otdelnym faylom — legko rasshirit bez troganiya servernoy storony.

Zemnoy abzats:
Eto kak operatorskiy terminal nad liniey: odna panel, odna knopka «Zapusk», ryadom — okno protokola.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_video_ui = Blueprint("video_ingest_ui", __name__)

@bp_video_ui.route("/admin/video", methods=["GET"])
def admin_video_page():
    return render_template("admin_video.html")

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_video_ui)