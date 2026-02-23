# -*- coding: utf-8 -*-
"""
routes/flight_review_routes.py - REST/UI «razbora poletov».

Ruchki:
  POST /flight_review/analyze {"events":[...]}
  POST /flight_review/overlay {"events":[...], "w":1280,"h":720}
  POST /flight_review/replay  {"events":[...], "speed":1.0}
  GET  /admin/flight_review

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.replay.flight_review import analyze, overlay, replay
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("flight_review_routes", __name__, url_prefix="/flight_review")

@bp.route("/analyze", methods=["POST"])
def a():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(analyze(list(d.get("events") or [])))

@bp.route("/overlay", methods=["POST"])
def o():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(overlay(list(d.get("events") or []), int(d.get("w",1280)), int(d.get("h",720))))

@bp.route("/replay", methods=["POST"])
def r():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(replay(list(d.get("events") or []), float(d.get("speed",1.0))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_flight_review.html")

def register(app):
    app.register_blueprint(bp)