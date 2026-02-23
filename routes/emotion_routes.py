# -*- coding: utf-8 -*-
"""
routes/emotion_routes.py - REST/UI dlya Emotion Tagging.

Mosty:
- Yavnyy: (UI ↔ Emotion) - dobavit metku, posmotret zapis/spisok/statistiku.
- Skrytyy 1: (Memory ↔ Sudeystvo) - affekt mozhet uchastvovat v ranzhirovanii vnutri «sudi».
- Skrytyy 2: (Nablyudaemost ↔ UX) - adminka daet bystryy vzglyad na emotsionalnyy profil.

Zemnoy abzats:
Forma iz neskolkikh poley: id, emotsiya, sila, zametka. Nazhal - metka sokhranilas.
Spiski pomogayut uvidet, chto «bolit» i chto «raduet».
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from modules.memory.emotion_tagging import tag, get, list_ids, stats
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("emotion_routes", __name__, url_prefix="/emotion")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.post("/tag")
def tag_():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(tag(str(d.get("id","") or ""), str(d.get("emotion","joy")), float(d.get("value", 0.0)), str(d.get("note",""))))

@bp.get("/get")
def get_():
    return jsonify(get(str(request.args.get("id","") or "")))

@bp.get("/list")
def list_():
    limit = int(request.args.get("limit", 100))
    return jsonify(list_ids(limit=limit))

@bp.get("/stats")
def stats_():
    return jsonify(stats())

@bp.get("/admin")
def admin():
    return render_template("admin_emotion.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b