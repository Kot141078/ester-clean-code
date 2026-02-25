# -*- coding: utf-8 -*-
"""routes/stream_overlay_routes.py - overley poverkh PNG-kadrov (VNC/noVNC sovmestimo).

Ruchki:
  POST /stream/overlay/arrow {"png_b64": "...", "from":[x,y], "to":[x,y], "label":"..."} -> {ok, png_b64}
  POST /stream/overlay/box {"png_b64": "...", "box":{"left":..,"top":..,"width":..,"height":..}, "label":..."} -> {ok, png_b64}

Primechanie:
  Zdes net klienta k VNC: kadr peredaetsya v tele zaprosa i vozvraschaetsya s razmetkoy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List
from modules.vision.stream_overlay import overlay_arrow, overlay_box
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("stream_overlay_routes", __name__, url_prefix="/stream/overlay")

@bp.route("/arrow", methods=["POST"])
def arrow():
    data = request.get_json(force=True, silent=True) or {}
    b64 = (data.get("png_b64") or "")
    p1 = data.get("from") or [40,40]
    p2 = data.get("to") or [200,120]
    lab = (data.get("label") or "")
    if not b64: return jsonify({"ok": False, "error": "png_b64_required"}), 400
    out = overlay_arrow(b64, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), lab or None)
    return jsonify({"ok": True, "png_b64": out})

@bp.route("/box", methods=["POST"])
def box():
    data = request.get_json(force=True, silent=True) or {}
    b64 = (data.get("png_b64") or "")
    box = data.get("box") or {"left":100,"top":100,"width":200,"height":80}
    lab = (data.get("label") or "")
    if not b64: return jsonify({"ok": False, "error": "png_b64_required"}), 400
    out = overlay_box(b64, {"left":int(box["left"]),"top":int(box["top"]),"width":int(box["width"]),"height":int(box["height"])}, lab or None)
    return jsonify({"ok": True, "png_b64": out})

def register(app):
    app.register_blueprint(bp)