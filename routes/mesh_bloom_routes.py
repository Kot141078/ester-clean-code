# -*- coding: utf-8 -*-
"""
routes/mesh_bloom_routes.py - REST: eksport/sliyanie/proverka Bloom-filtra.

Mosty:
- Yavnyy: (Veb ↔ P2P) legkiy obmen filtrami mezhdu uzlami.
- Skrytyy #1: (Ingest ↔ Ekonomiya) ne kachaem dubl-fayly.
- Skrytyy #2: (Resilience ↔ Prostota) stateless-ruchki bez pobochnykh effektov.

Zemnoy abzats:
«Vy uzhe eto slali?» - sprashivaem filtr, a ne set.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mesh_bloom_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mesh.bloom import export as _exp, merge as _merge, check as _check, add as _add  # type: ignore
except Exception:
    _exp=_merge=_check=_add=None  # type: ignore

@bp.route("/mesh/bloom", methods=["GET"])
def api_get():
    if _exp is None: return jsonify({"ok": False, "error":"bloom_unavailable"}), 500
    return jsonify({"ok": True, **_exp()})

@bp.route("/mesh/bloom/merge", methods=["POST"])
def api_merge():
    if _merge is None: return jsonify({"ok": False, "error":"bloom_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_merge(list(d.get("bits") or [])))

@bp.route("/mesh/bloom/check", methods=["POST"])
def api_check():
    if _check is None: return jsonify({"ok": False, "error":"bloom_unavailable"}), 500
    d=request.get_json(True, True) or {}
    rep=_check(str(d.get("id","")))
    if rep.get("maybe_seen") is False:
        try:
            _add(str(d.get("id","")))
        except Exception:
            pass
    return jsonify(rep)
# c=a+b