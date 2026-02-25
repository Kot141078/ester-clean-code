# -*- coding: utf-8 -*-
"""routes/mem_maint_routes.py - REST: heal/compact/snapshot/reindex.

Mosty:
- Yavnyy: (Veb ↔ TO pamyati) ruchki dlya kron-zadach i ruchnogo zapuska.
- Skrytyy #1: (Profile ↔ Audit) operatsii fiksiruyutsya.
- Skrytyy #2: (RBAC ↔ Ostorozhnost) mozhno zaschitit vysokoy rolyu pri zhelanii.

Zemnoy abzats:
Te samye knopki “Pochinit”, “Szhat”, “Sdelat snimok”, “Pereindeksirovat”.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mem_maint_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.maintenance import heal as _heal, compact as _compact, snapshot as _snapshot, reindex as _reindex  # type: ignore
except Exception:
    _heal=_compact=_snapshot=_reindex=None  # type: ignore

@bp.route("/mem/maint/heal", methods=["POST"])
def api_heal():
    if _heal is None: return jsonify({"ok": False, "error":"maint_unavailable"}), 500
    return jsonify(_heal())

@bp.route("/mem/maint/compact", methods=["POST"])
def api_compact():
    if _compact is None: return jsonify({"ok": False, "error":"maint_unavailable"}), 500
    return jsonify(_compact())

@bp.route("/mem/maint/snapshot", methods=["POST"])
def api_snapshot():
    if _snapshot is None: return jsonify({"ok": False, "error":"maint_unavailable"}), 500
    return jsonify(_snapshot())

@bp.route("/mem/maint/reindex", methods=["POST"])
def api_reindex():
    if _reindex is None: return jsonify({"ok": False, "error":"maint_unavailable"}), 500
    return jsonify(_reindex())
# c=a+b