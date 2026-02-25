# -*- coding: utf-8 -*-
"""routes/video_subs_routes.py - REST CRUD dlya podpisok video: /proactive/video/subs*.

Mosty:
- Yavnyy: (UX v†" Proaktiv) Upravlenie istochnikami pryamo iz interfeysov/skriptov bez pravki faylov vruchnuyu.
- Skrytyy #1: (Kibernetika v†" Nadezhnost) Validatsiya Re idempotent upsert predotvraschayut "drozhanie" konfiguratsii.
- Skrytyy #2: (Infoteoriya v†" Memory) Config - dolgovremennyy istochnik pritoka dannykh v pamyat, redaktiruemyy bezopasno.

Zemnoy abzats:
Eto kak vynos upravlyayuschikh ventiley na schit: vklyuchit trubu, change filtr, ogranichit potok - bez perekladki kabeley.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.proactive.video_subs_cfg import load_all, upsert, delete as cfg_delete, toggle as cfg_toggle  # type: ignore
except Exception:
    load_all = upsert = cfg_delete = cfg_toggle = None  # type: ignore

bp_video_subs = Blueprint("video_subs", __name__)

def _err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code

@bp_video_subs.route("/proactive/video/subs", methods=["GET"])
def list_subs():
    if load_all is None:
        return _err("config module not available", 500)
    try:
        return jsonify({"ok": True, "subscriptions": load_all()})
    except Exception as e:
        return _err(f"exception: {e}", 500)

@bp_video_subs.route("/proactive/video/subs", methods=["POST"])
def upsert_sub():
    if upsert is None:
        return _err("config module not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        ent = upsert(data)
        return jsonify({"ok": True, "subscription": ent})
    except Exception as e:
        return _err(f"exception: {e}", 400)

@bp_video_subs.route("/proactive/video/subs/<sub_id>", methods=["DELETE"])
def delete_sub(sub_id: str):
    if cfg_delete is None:
        return _err("config module not available", 500)
    try:
        ok = cfg_delete(sub_id)
        if not ok:
            return _err("not found", 404)
        return jsonify({"ok": True})
    except Exception as e:
        return _err(f"exception: {e}", 500)

@bp_video_subs.route("/proactive/video/subs/<sub_id>/toggle", methods=["POST"])
def toggle_sub(sub_id: str):
    if cfg_toggle is None:
        return _err("config module not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        enabled = int(data.get("enabled", 0))
        ent = cfg_toggle(sub_id, enabled)
        return jsonify({"ok": True, "subscription": ent})
    except KeyError:
        return _err("not found", 404)
    except Exception as e:
        return _err(f"exception: {e}", 500)

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_video_subs)