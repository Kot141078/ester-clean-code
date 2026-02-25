# -*- coding: utf-8 -*-
"""routes/multi_leader_routes.py - REST/UI dlya multi-lidera.

Ruchki:
  POST /multi_leader/create {"room":"r","leader":"alice"}
  POST /multi_leader/add {"room":"r","user":"bob"}
  POST /multi_leader/baton {"room":"r","to":"bob"}
  POST /multi_leader/rotate {"room":"r"}
  GET /multi_leader/status?room=r
  GET /admin/multi_leader

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.multi_leader import create, add, baton, rotate, status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("multi_leader_routes", __name__, url_prefix="/multi_leader")

@bp.route("/create", methods=["POST"])
def c():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(create(str(d.get("room","")), str(d.get("leader",""))))

@bp.route("/add", methods=["POST"])
def a():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(add(str(d.get("room","")), str(d.get("user",""))))

@bp.route("/baton", methods=["POST"])
def b():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(baton(str(d.get("room","")), str(d.get("to",""))))

@bp.route("/rotate", methods=["POST"])
def r():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(rotate(str(d.get("room",""))))

@bp.route("/status", methods=["GET"])
def s():
    return jsonify(status(str(request.args.get("room",""))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_multi_leader.html")

def register(app):
    app.register_blueprint(bp)