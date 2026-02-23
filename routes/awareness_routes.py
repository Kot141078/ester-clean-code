# -*- coding: utf-8 -*-
"""
routes/awareness_routes.py - REST: samoosoznannost (inventarizatsiya/graf).

Mosty:
- Yavnyy: (Veb ↔ Samosoznanie) bystro uznat sostav i sha256.
- Skrytyy #1: (Audit ↔ Kontrol) prigodno dlya proverok pered deploem.
- Skrytyy #2: (Planirovanie ↔ Moduli) osnova dlya podbora deystviy.

Zemnoy abzats:
Knopka «chto vo mne est?».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_aware = Blueprint("awareness", __name__)

try:
    from modules.self.awareness import status as _status, graph as _graph  # type: ignore
except Exception:
    _status = _graph = None  # type: ignore

def register(app):
    app.register_blueprint(bp_aware)

@bp_aware.route("/self/awareness/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"awareness unavailable"}), 500
    return jsonify(_status())

@bp_aware.route("/self/awareness/graph", methods=["GET"])
def api_graph():
    if _graph is None: return jsonify({"ok": False, "error":"awareness unavailable"}), 500
    return jsonify(_graph())
# c=a+b