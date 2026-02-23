# -*- coding: utf-8 -*-
"""
routes/social_kit_routes.py - REST: sborka i spisok export-kit'ov.

Mosty:
- Yavnyy: (Veb ↔ Kit) odna knopka sobiraet komplekt dlya publikatsii.
- Skrytyy #1: (Profile ↔ Memory) sborka uzhe logiruetsya modulem.
- Skrytyy #2: (Volya ↔ Avtomatizatsiya) te zhe funktsii dostupny ekshenami.

Zemnoy abzats:
Eto kak «upakovat reliz»: vse nuzhnoe - v odnu papku, gotovo k vygruzke.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("social_kit_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.social.kit import build as _build, list_kits as _list  # type: ignore
except Exception:
    _build=_list=None  # type: ignore

@bp.route("/social/kit/build", methods=["POST"])
def api_build():
    if _build is None: return jsonify({"ok": False, "error":"kit_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_build(
        str(d.get("platform","youtube")),
        str(d.get("title","Untitled")),
        str(d.get("description","")),
        list(d.get("tags") or []),
        dict(d.get("media") or {})
    ))

@bp.route("/social/kit/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"kit_unavailable"}), 500
    return jsonify(_list())
# c=a+b