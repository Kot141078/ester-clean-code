# -*- coding: utf-8 -*-
"""
routes/attention_playlist_routes.py - REST/UI dlya pleylistov vnimaniya.

Ruchki:
  POST /playlist/run  {"spec":{...},"peers":["127.0.0.1:8000"]}
  POST /playlist/stop {}
  GET  /playlist/status
  GET  /admin/playlists

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.attention_playlist import run as pl_run, stop as pl_stop, status as pl_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("attention_playlist_routes", __name__, url_prefix="/playlist")

@bp.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(pl_run(data.get("spec") or {}, list(data.get("peers") or [])))

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(pl_stop())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(pl_status())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_playlists.html")

def register(app):
    app.register_blueprint(bp)
