# -*- coding: utf-8 -*-
"""routes/attention_routes.py - “ochki vnimaniya” (kooperativnaya podsvetka).

Ruchki:
  POST /attention/arrow {"from":[x,y],"to":[x,y],"label":"Syuda","peers":["127.0.0.1:8000"]}
  POST /attention/box {"box":{"left":..,"top":..,"width":..,"height":..},"label":"Pole","peers":[...]}
  GET /attention/history

UI: /admin/attention - prostaya panel.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict, List
from modules.coop.attention import set_arrow, set_box, history
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("attention_routes", __name__, url_prefix="/attention")

@bp.route("/arrow", methods=["POST"])
def arrow():
    data = request.get_json(force=True, silent=True) or {}
    p1 = data.get("from") or [40,40]; p2 = data.get("to") or [200,120]; label = (data.get("label") or "")
    peers = list(data.get("peers") or [])
    return jsonify(set_arrow((int(p1[0]),int(p1[1])), (int(p2[0]),int(p2[1])), label, peers, True))

@bp.route("/box", methods=["POST"])
def box():
    data = request.get_json(force=True, silent=True) or {}
    box = data.get("box") or {"left":100,"top":100,"width":200,"height":80}
    label = (data.get("label") or "")
    peers = list(data.get("peers") or [])
    return jsonify(set_box({"left":int(box["left"]),"top":int(box["top"]),"width":int(box["width"]),"height":int(box["height"])}, label, peers, True))

@bp.route("/history", methods=["GET"])
def hist():
    return jsonify(history())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_attention.html")

def register(app):
    app.register_blueprint(bp)
