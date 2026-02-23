# -*- coding: utf-8 -*-
"""
routes/sense_routes.py - REST-ruchki sensoriki.

Ruchki:
  GET /sense/journal/tail?n=100
  GET /sense/screen/snap?w=640&h=360
  GET /sense/windows/list
  GET /sense/proc/list?like=notepad
  GET /admin/sense

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.sense.collect import journal_tail, screen_snap, windows_list, proc_list
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("sense_routes", __name__, url_prefix="/sense")

@bp.route("/journal/tail", methods=["GET"])
def jtail():
    n = int(request.args.get("n", 100))
    return jsonify(journal_tail(n))

@bp.route("/screen/snap", methods=["GET"])
def snap():
    w = int(request.args.get("w", 0) or 0)
    h = int(request.args.get("h", 0) or 0)
    return jsonify(screen_snap(w, h))

@bp.route("/windows/list", methods=["GET"])
def winlist():
    return jsonify(windows_list())

@bp.route("/proc/list", methods=["GET"])
def proclist():
    like = request.args.get("like")
    return jsonify(proc_list(like))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_sense.html")

def register(app):
    app.register_blueprint(bp)