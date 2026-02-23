# -*- coding: utf-8 -*-
"""
routes/viz_routes.py - REST/UI dlya vizualizatsii planov (ASCII).

Mosty:
- Yavnyy: (UI ↔ Visualizer) - otdaem ascii-blok po zagolovku i shagam.
- Skrytyy 1: (Obyasnimost ↔ Logi) - tekst skhemy legko lozhitsya v fayl/chat/pismo.
- Skrytyy 2: (Memory ↔ Prezentatsii) - mozhno keshirovat skhemy v otchetakh.

Zemnoy abzats:
Knopka «skhema»: poluchil blok, vstavil v otchet ili otpravil v chat. Nikakikh zavisimostey, vse tekstom.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from typing import List
from modules.cognition.visualizer import render_plan
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("viz_routes", __name__, url_prefix="/viz")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.post("/plan")
def plan():
    d = request.get_json(force=True, silent=True) or {}
    title = str(d.get("title","") or "")
    steps: List[str] = list(d.get("steps") or [])
    return jsonify(render_plan(title=title, steps=steps))

@bp.get("/admin")
def admin():
    return render_template("admin_viz.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b