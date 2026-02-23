# -*- coding: utf-8 -*-
"""
routes/game_binding_routes.py - REST/UI dlya privyazki multi-lidera k game_sync.

Ruchki:
  POST /binding/bind     {"room":"test","leader":"alice","tick_rate":20,"quota":5}
  POST /binding/follow   {"flag":true}
  POST /binding/refresh  {"room":"test"}
  GET  /binding/status
  GET  /admin/binding

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.game_binding import bind, follow_ml, refresh, status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("game_binding_routes", __name__, url_prefix="/binding")

@bp.route("/bind", methods=["POST"])
def b():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(bind(str(d.get("room","")), str(d.get("leader","")), int(d.get("tick_rate",20)), int(d.get("quota",5))))

@bp.route("/follow", methods=["POST"])
def f():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(follow_ml(bool(d.get("flag", True))))

@bp.route("/refresh", methods=["POST"])
def r():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(refresh(d.get("room")))

@bp.route("/status", methods=["GET"])
def s():
    return jsonify(status())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_binding.html")

def register(app):
    app.register_blueprint(bp)