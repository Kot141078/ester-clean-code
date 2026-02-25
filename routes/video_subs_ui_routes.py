# -*- coding: utf-8 -*-
"""routes/video_subs_ui_routes.py - UI-stranitsa /admin/video/subs: CRUD po podpiskam.

Mosty:
- Yavnyy: (UX v†" Konveyer) R edaktor podpisok ryadom s pultom analiza - operator vidit vkhod Re mozhet im upravlyat.
- Skrytyy #1: (Logika v†" Planirovschik) Tumbler enabled opredelyaet uchastie istochnika v obkhodakh bez perezapuska sistemy.
- Skrytyy #2: (Inzheneriya v†" Ekspluatatsiya) Minimalnyy chistyy HTML/JS, otdelennyy ot servernoy logiki - prosto podderzhivat.

Zemnoy abzats:
Eto kak stol dispetchera s reestrom postavschikov: vklyuchit liniyu, vyklyuchit, popravit limity - vse v odnom okne.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_video_subs_ui = Blueprint("video_subs_ui", __name__)

@bp_video_subs_ui.route("/admin/video/subs", methods=["GET"])
def admin_video_subs():
    return render_template("admin_video_subs.html")

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_video_subs_ui)