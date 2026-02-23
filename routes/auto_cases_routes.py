# -*- coding: utf-8 -*-
"""
routes/auto_cases_routes.py - REST dlya avtogeneratsii UI-testov.

Ruchki:
  POST /auto/tests/mine    {"timeout_ms":2000}
  POST /auto/tests/install {"timeout_ms":2000}

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.test.auto_cases import mine, install
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auto_cases_routes", __name__, url_prefix="/auto/tests")

@bp.route("/mine", methods=["POST"])
def m():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(mine(int(data.get("timeout_ms", 2000))))

@bp.route("/install", methods=["POST"])
def i():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(install(int(data.get("timeout_ms", 2000))))

def register(app):
    app.register_blueprint(bp)