# -*- coding: utf-8 -*-
"""
routes/triggers_routes.py - REST/UI dlya triggerov ekrana.

Ruchki:
  GET  /triggers/list
  POST /triggers/add    {"kind":"ocr_contains","cond":{"text":"Privet","lang":"eng+rus"},"action":{"type":"macro","name":"type_text","args":{"text":"OK"}}}
  POST /triggers/clear
  POST /triggers/start  {"interval_ms":600}
  POST /triggers/stop
  GET  /triggers/status

UI: /admin/triggers

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict
from modules.vision.triggers import list_triggers, add_trigger, clear_triggers, start as tr_start, stop as tr_stop, status as tr_status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("triggers_routes", __name__, url_prefix="/triggers")

@bp.route("/list", methods=["GET"])
def lst():
    return jsonify({"ok": True, "triggers": list_triggers()})

@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(add_trigger(data))

@bp.route("/clear", methods=["POST"])
def clr():
    return jsonify(clear_triggers())

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(tr_start(int(data.get("interval_ms", 800))))

@bp.route("/stop", methods=["POST"])
def stop():
    return jsonify(tr_stop())

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(tr_status())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_triggers.html")

def register(app):
    app.register_blueprint(bp)