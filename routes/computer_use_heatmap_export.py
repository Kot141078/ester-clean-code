# -*- coding: utf-8 -*-
"""
routes/computer_use_heatmap_export.py - REST-eksport predlozheniy yakorey iz heatmap.

MOSTY:
- Yavnyy: (CLI/UI ↔ Anchors Suggestions) - odnoy knopkoy formiruem nabor predlozheniy.
- Skrytyy №1: (Analitika ↔ Protsedury) - opiraemsya na realnye logi za okno vremeni.
- Skrytyy №2: (Bezopasnost ↔ Sovmestimost) - pishem v suggestions, ne trogaem boevuyu bazu yakorey.

ZEMNOY ABZATs:
Eto «generator yarlykov»: chastye tseli prevraschayutsya v kandidatov-yakorya, kotorye mozhno obsudit i prinyat vruchnuyu.

c=a+b
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
from modules.computer_use.anchors_suggest import export as export_anchors
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("computer_use_heatmap_export", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.route("/computer_use/heatmap/export_anchors", methods=["POST"])
def heatmap_export_anchors():
    d = request.get_json(force=True, silent=True) or {}
    domain = (d.get("domain") or "").strip().lower()
    if not domain:
        return jsonify({"ok": False, "error": "domain required"}), 400
    window = (d.get("window") or "30d").strip()
    top = int(d.get("top") or 20)
    prefix = (d.get("prefix") or "auto").strip().lower()
    r = export_anchors(domain, window=window, top=top, prefix=prefix)
    return (jsonify(r), 200 if r.get("ok") else 400)

# c=a+b