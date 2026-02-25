# -*- coding: utf-8 -*-
"""routes/ops_summary_routes.py - REST: /ops/summary

Mosty:
- Yavnyy: (Veb ↔ Operatsii) odna ruchka vozvraschaet kompaktnuyu svodku sostoyaniya.
- Skrytyy #1: (Panel ↔ UX) udobno risovat dashbord v UI.
- Skrytyy #2: (Samorazvitie ↔ Volya) po svodke “puls” mozhet prinimat resheniya (for example, usilit ingest).

Zemnoy abzats:
Otkryl "priborku" - uvidel vse vazhnoe srazu.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ops_summary_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.ops.summary import make_summary as _make  # type: ignore
except Exception:
    _make=None  # type: ignore

@bp.route("/ops/summary", methods=["GET"])
def api_summary():
    if _make is None: return jsonify({"ok": False, "error":"ops_summary_unavailable"}), 500
    return jsonify(_make())
# c=a+b