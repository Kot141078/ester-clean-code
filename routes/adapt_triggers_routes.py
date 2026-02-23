# -*- coding: utf-8 -*-
"""
routes/adapt_triggers_routes.py - REST-pult adaptivnykh triggerov.

Ruchki:
  POST /adapt/observe {"result":"hit|miss","thr":0.74,"meta":{...}}
  GET  /adapt/threshold -> {value}
  POST /adapt/seed_template {"thr":0.78,"n":5}  # zanesti N "hit" tochek dlya razgona

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.vision.adapt_triggers import keep_observation, current_threshold
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("adapt_triggers_routes", __name__, url_prefix="/adapt")

@bp.route("/observe", methods=["POST"])
def observe():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(keep_observation(data.get("result","miss"), float(data.get("thr", 0.78)), data.get("meta") or {}))

@bp.route("/threshold", methods=["GET"])
def threshold():
    return jsonify({"ok": True, "value": current_threshold()})

@bp.route("/seed_template", methods=["POST"])
def seed():
    data = request.get_json(force=True, silent=True) or {}
    thr = float(data.get("thr", 0.78)); n = int(data.get("n", 5))
    for _ in range(max(0,n)):
        keep_observation("hit", thr, {"seed": True})
    return jsonify({"ok": True, "count": n, "value": current_threshold()})

def register(app):
    app.register_blueprint(bp)