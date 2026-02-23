# -*- coding: utf-8 -*-
"""
routes/studio_avatar_routes.py - REST: reestr modeley i «virtualnyy veduschiy».

Mosty:
- Yavnyy: (Veb ↔ Orkestrator) pokazyvaet dostupnye provaydery i renderit veduschego.
- Skrytyy #1: (Politiki ↔ Soglasie) zapreschaet realnyy lik bez consent.
- Skrytyy #2: (Memory ↔ Profile) logiruet fakt vypuska.

Zemnoy abzats:
Knopki «proverit dvizhki» i «sobrat veduschego» - i vsya magiya pod kapotom.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("studio_avatar_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.studio.models.registry import list_providers as _list, select as _select  # type: ignore
    from modules.studio.avatar import make as _make  # type: ignore
except Exception:
    _list=_select=_make=None  # type: ignore

@bp.route("/studio/models", methods=["GET"])
def api_models():
    if _list is None: return jsonify({"ok": False, "error":"orchestrator_unavailable"}), 500
    return jsonify({"ok": True, "providers": _list()})

@bp.route("/studio/avatar/make", methods=["POST"])
def api_avatar():
    if _make is None: return jsonify({"ok": False, "error":"orchestrator_unavailable"}), 500
    d=request.get_json(True, True) or {}
    rep=_make(str(d.get("title","Host")), list(d.get("script") or []), dict(d.get("avatar") or {}), dict(d.get("tts") or {}), bool(d.get("consent", False)))
    # profile
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, json.dumps({"title": d.get("title"), "ok": rep.get("ok")}, ensure_ascii=False), {"kind":"avatar_make"}, source="studio://avatar")
    except Exception:
        pass
    return jsonify(rep)
# c=a+b