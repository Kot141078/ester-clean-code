# -*- coding: utf-8 -*-
"""
routes/self_manifest_routes.py - REST: /self/manifest (GET: tolko karta; POST: sobrat i pri zhelanii zapisat v pamyat)

Mosty:
- Yavnyy: (Veb ↔ Samosoznanie) daet dostup k SelfMap Ester.
- Skrytyy #1: (Memory ↔ Profile) po POST so store=true sokhranyaet kartu v pamyat.
- Skrytyy #2: (RAG ↔ Navyki) karta prigodna dlya bystrogo otveta «chto u menya est».

Zemnoy abzats:
Sprosili - «kto ya i iz chego sobrana?» - i poluchili tochnuyu kartu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("self_manifest_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.self.manifest import build_selfmap as _build, store_selfmap as _store  # type: ignore
except Exception:
    _build=_store=None  # type: ignore

@bp.route("/self/manifest", methods=["GET","POST"])
def api_manifest():
    if _build is None: return jsonify({"ok": False, "error":"self_manifest_unavailable"}), 500
    if request.method=="GET":
        return jsonify(_build())
    d=request.get_json(True, True) or {}
    store=bool(d.get("store", False))
    if store and _store is not None:
        rep=_store()
        return jsonify({"ok": bool(rep.get("ok",False)), "stored": rep})
    return jsonify(_build())
# c=a+b