# -*- coding: utf-8 -*-
"""routes/model_registry_routes.py - REST: proverka dopuska modeli /models/verify?id=...

Mosty:
- Yavnyy: (Bezopasnost ↔ Web) tsentralizuet politiku dostupa k modelyam cherez edinyy REST.
- Skrytyy #1: (Logika ↔ Kontrakty) determinirovannyy JSON-otvet dlya avtomaticheskikh proverok.
- Skrytyy #2: (Memory/Audit ↔ Prozrachnost) legko podklyuchaetsya “profile” dlya zhurnalirovaniya.
- Skrytyy #3: (Kibernetika ↔ Kontrol) bystryy predikat dopuska vstraivaetsya v payplayny.

Zemnoy abzats:
Dumay o module kak o “turnikete” v servernoy: na vkhod podayut model_id - turniket govorit,
mozhno li prokhodit i chto izvestno o modeli (meta). Just i nadezhnyy predikat.

c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import reestra
try:
    from modules.security.model_registry import allowed as _allowed, get as _get  # type: ignore
except Exception:  # pragma: no cover
    _allowed = _get = None  # type: ignore

bp_models = Blueprint("models", __name__, url_prefix="/models")


@bp_models.get("/verify")
def verify():
    model_id = (request.args.get("id") or "").strip()
    if not model_id:
        return jsonify({"ok": False, "error": "missing id"}), 400
    if _allowed is None or _get is None:
        return jsonify({"ok": False, "error": "model_registry unavailable"}), 500
    try:
        return jsonify(
            {
                "ok": True,
                "id": model_id,
                "allowed": bool(_allowed(model_id)),
                "meta": _get(model_id),
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (project contract)."""
    app.register_blueprint(bp_models)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp_models", "register", "init_app"]
# c=a+b