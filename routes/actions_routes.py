# -*- coding: utf-8 -*-
"""
routes/actions_routes.py - REST dlya Action Hooks (create_note, set_tag, publish_tg_preview).

Mosty:
- Yavnyy: (Marshruty ↔ Deystviya) HTTP-ruchki transliruyut vyzovy v modules.action_hooks.* bez izmeneniy kontraktov.
- Skrytyy #1: (Faylovaya pamyat ↔ Dannye) vse operatsii bezopasny offlayn i pishut na disk.
- Skrytyy #2: (RBAC ↔ Nablyudaemost) podderzhka optional JWT i stabilnye JSON-otvety dlya zhurnalirovaniya.

Zemnoy abzats:
Eto «klemmnaya kolodka»: prostye vinty/kontakty dlya deystviy. Skrutil - derzhitsya, prozvonil - tok techet.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict

from flask import Blueprint, jsonify, request

# JWT - optsionalno
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn): return fn
        return _wrap

# Bekend deystviy (drop-in)
from modules.action_hooks import create_note, set_tag, publish_tg_preview  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Globalnyy BP (dlya avtozagruzchika) i registratsiya
bp = Blueprint("actions_routes", __name__, url_prefix="/actions")


@bp.post("/create_note")
@jwt_required(optional=True)
def action_create_note():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    text = str(data.get("text", ""))
    tags = list(data.get("tags") or [])
    meta = dict(data.get("meta") or {})
    try:
        res = create_note(text, tags=tags, meta=meta)
        return jsonify(res)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/set_tag")
@jwt_required(optional=True)
def action_set_tag():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    target = str(data.get("target", ""))
    tag = str(data.get("tag", ""))
    try:
        res = set_tag(target, tag)
        return jsonify(res)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/publish_tg_preview")
@jwt_required(optional=True)
def action_publish_tg_preview():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    text = str(data.get("text", ""))
    chat_id = data.get("chat_id")
    if not text:
        return jsonify({"ok": False, "error": "text required"}), 400
    try:
        res = publish_tg_preview(text, chat_id)
        return jsonify(res)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


def register(app) -> None:
    """Standartnyy registrator dlya avtozagruzchika."""
    # bezopasnaya registratsiya: povtornaya ne padaet
    name = bp.name
    if name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp)


def register(app):
    app.register_blueprint(bp)
    return app