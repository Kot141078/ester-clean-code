# -*- coding: utf-8 -*-
"""routes/director_routes.py - REST+UI dlya "zhivogo rezhissera".

Ruchki:
  POST /director/start {"topic":"..."} -> {session, steps}
  POST /director/chat {"session":"..","text":".."} -> {suggestions}
  POST /director/suggest {"session":".."} -> {step}
  POST /director/apply {"session":"..","step":{...}} -> {count}
  POST /director/overlay {"session":"..","index":0,"template_b64"?:...,"threshold"?:0.78} -> {overlay_b64}
  POST /director/run {"session":"..","index":0} -> {ok}

UI:
  GET /admin/director

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict

from modules.thinking.director import start as _start, chat as _chat, suggest as _suggest, apply as _apply, overlay as _overlay, run as _run
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("director_routes", __name__, url_prefix="/director")

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"ok": False, "error": "topic_required"}), 400
    return jsonify(_start(topic))

@bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_chat(data.get("session",""), data.get("text","")))

@bp.route("/suggest", methods=["POST"])
def suggest():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_suggest(data.get("session","")))

@bp.route("/apply", methods=["POST"])
def apply():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_apply(data.get("session",""), data.get("step") or {}))

@bp.route("/overlay", methods=["POST"])
def overlay():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_overlay(data.get("session",""), int(data.get("index",0)), data.get("template_b64"), float(data.get("threshold", 0.78))))

@bp.route("/run", methods=["POST"])
def run():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_run(data.get("session",""), int(data.get("index",0))))

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_director.html")

def register(app):
    app.register_blueprint(bp)