# -*- coding: utf-8 -*-
"""routes/self_awareness_routes.py - REST: samoosoznanie (inventar i graf).

Mosty:
- Yavnyy: (Veb ↔ Samopoznanie) bystryy dostup k inventaryu i grafu zavisimostey.
- Skrytyy #1: (Audit ↔ DevOps) prigodno dlya proverki tselostnosti i poiska podmen.
- Skrytyy #2: (Kibernetika ↔ Planning) osnova dlya avtogeneratsii deystviy.

Zemnoy abzats:
Odin zapros - i see, chem my yavlyaemsya i kak ustroeny.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_aw = Blueprint("self_awareness", __name__)

try:
    from modules.self.awareness import scan_inventory as _scan, build_graph as _graph  # type: ignore
except Exception:
    _scan = _graph = None  # type: ignore

def register(app):
    app.register_blueprint(bp_aw)

@bp_aw.route("/self/awareness/status", methods=["GET"])
def api_status():
    if _scan is None: return jsonify({"ok": False, "error":"awareness_unavailable"}), 500
    return jsonify(_scan())

@bp_aw.route("/self/awareness/graph", methods=["GET"])
def api_graph():
    if _graph is None: return jsonify({"ok": False, "error":"awareness_unavailable"}), 500
    return jsonify(_graph())
# c=a+b