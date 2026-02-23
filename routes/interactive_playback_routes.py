# -*- coding: utf-8 -*-
"""
routes/interactive_playback_routes.py - REST/UI dlya interaktivnogo pleybeka.

Ruchki:
  POST /iplay/load  {"steps":[...]}
  POST /iplay/start {}
  POST /iplay/pause {}
  POST /iplay/resume {}
  POST /iplay/stop {}
  POST /iplay/next {}
  POST /iplay/prev {}
  GET  /iplay/status
  GET  /admin/playback

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.coop.interactive_playback import load as iload, start as istart, pause as ipause, resume as iresume, stop as istop, next_step as inext, prev_step as iprev, status as istatus
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("interactive_playback_routes", __name__, url_prefix="/iplay")

@bp.route("/load", methods=["POST"])
def load():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(iload(list(data.get("steps") or [])))

@bp.route("/start", methods=["POST"])
def start():
    return jsonify(istart())

@bp.route("/pause", methods=["POST"])
def pause():
    return jsonify(ipause())

@bp.route("/resume", methods=["POST"])
def resume():
    return jsonify(iresume())

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(istop())

@bp.route("/next", methods=["POST"])
def nxt():
    return jsonify(inext())

@bp.route("/prev", methods=["POST"])
def prv():
    return jsonify(iprev())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(istatus())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_playback.html")

def register(app):
    app.register_blueprint(bp)