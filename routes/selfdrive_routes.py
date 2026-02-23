# -*- coding: utf-8 -*-
"""
routes/selfdrive_routes.py - REST/UI dlya rezhima samovedeniya (SelfDrive).

Ruchki:
  POST /thinking/selfdrive/run_once  {"goal":"...", "params":{...}}
  POST /thinking/selfdrive/enable
  POST /thinking/selfdrive/disable
  GET  /thinking/selfdrive/status
  GET  /thinking/selfdrive/log
  GET  /admin/selfdrive

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.thinking import selfdrive as SD
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("selfdrive_routes", __name__, url_prefix="/thinking/selfdrive")

@bp.route("/run_once", methods=["POST"])
def run_once():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(SD.run_once(d.get("goal",""), d.get("params") or {}))

@bp.route("/enable", methods=["POST"])
def enable():
    return jsonify(SD.enable())

@bp.route("/disable", methods=["POST"])
def disable():
    return jsonify(SD.disable())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(SD.status())

@bp.route("/log", methods=["GET"])
def log():
    return jsonify(SD.log())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_selfdrive.html")

def register(app):
    app.register_blueprint(bp)