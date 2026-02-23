# routes/mem_affect_routes.py
# -*- coding: utf-8 -*-
"""
routes/mem_affect_routes.py - REST: pereschet vesov po affektu i affect-aware refleksiya.

Mosty:
- Yavnyy (Veb ↔ Memory/Refleksiya): bystryy pereschet prioriteta - «snachala vazhnoe po emotsiyam».
- Skrytyy #1 (Refleksiya ↔ Planirovschik): mozhno zapuskat iz «pulsa»/scheduler.
- Skrytyy #2 (RAG ↔ Vospominanie): downstream drayvery mogut uchityvat fayl vesov.
- Skrytyy #3 (Memory ↔ Profile): logiruetsya vybor top-elementov.

Zemnoy abzats:
HTTP-ruchki dlya perescheta vazhnosti i otbora top-elementov s uchetom emotsionalnoy relevantnosti. Prostoy JSON-vyzov - i u Ester obnovlennye prioritety.
# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_affect", __name__)

try:
    from modules.mem.affect_reprioritize import recalc as _rep  # type: ignore
except Exception:
    _rep = None  # type: ignore

try:
    from modules.mem.affect_reflection import prioritize as _prior  # type: ignore
except Exception:
    _prior = None  # type: ignore

@bp.route("/mem/affect/reprioritize", methods=["POST"])
def api_rep():
    if _rep is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_rep(int(d.get("top", 100))))

@bp.route("/mem/reflect/affect", methods=["POST"])
def api_affect():
    if _prior is None:
        return jsonify({"ok": False, "error": "affect_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_prior(list(d.get("items") or []), int(d.get("top_k", 5))))

def register_routes(app, seen_endpoints=None):
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app