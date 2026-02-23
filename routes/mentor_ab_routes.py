# -*- coding: utf-8 -*-
"""
routes/mentor_ab_routes.py - pult A/B «Nastavnika».

Ruchki:
  GET  /mentor/ab/status
  POST /mentor/ab/switch {"slot":"A"|"B"}
  POST /mentor/ab/auto   {"sec":60}
  POST /mentor/ab/cancel_auto

UI: /admin/mentorab - prostaya stranitsa upravleniya.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking.mentor_ab import status as st, switch as sw, set_auto as sa, cancel_auto as ca
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mentor_ab_routes", __name__)

@bp.route("/mentor/ab/status", methods=["GET"])
def status():
    return jsonify({"ok": True, **st()})

@bp.route("/mentor/ab/switch", methods=["POST"])
def switch():
    slot = (request.get_json(force=True, silent=True) or {}).get("slot","A")
    res = sw(slot)
    code = 200 if res.get("ok") else 400
    return jsonify(res), code

@bp.route("/mentor/ab/auto", methods=["POST"])
def auto():
    data = request.get_json(force=True, silent=True) or {}
    sec = int(data.get("sec", 0) or 0)
    return jsonify(sa(sec))

@bp.route("/mentor/ab/cancel_auto", methods=["POST"])
def cancel_auto():
    return jsonify(ca())

@bp.route("/admin/mentorab", methods=["GET"])
def admin():
    return render_template("admin_recorder.html")  # obschiy UI s vkladkoy AB
def register(app):
    app.register_blueprint(bp)