# -*- coding: utf-8 -*-
"""
routes/ui_cases_routes.py - REST/UI dlya vizualnykh test-keysov.

Ruchki:
  POST /ui/cases/add   {"name":"..","kind":"ocr_contains","params":{"text":"Fayl","lang":"rus+eng"},"timeout_ms":2000}
  GET  /ui/cases/list
  POST /ui/cases/clear
  POST /ui/cases/run
  GET  /ui/cases/export

UI: /admin/ui_tests

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from modules.test.ui_cases import add_case, list_cases, clear_cases, run_all, export_json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ui_cases_routes", __name__, url_prefix="/ui/cases")

@bp.route("/add", methods=["POST"])
def add():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(add_case(data))

@bp.route("/list", methods=["GET"])
def lst():
    return jsonify(list_cases())

@bp.route("/clear", methods=["POST"])
def clr():
    return jsonify(clear_cases())

@bp.route("/run", methods=["POST"])
def run():
    return jsonify(run_all())

@bp.route("/export", methods=["GET"])
def exp():
    return jsonify(export_json())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_ui_tests.html")

def register(app):
    app.register_blueprint(bp)