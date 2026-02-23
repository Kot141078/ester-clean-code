# -*- coding: utf-8 -*-
"""
routes/rate_limiter_routes.py - REST dlya rate limit.

Ruchki:
  POST /rate/limit/set {"key":"hotkey","limit_per_min":30}
  GET  /rate/limit/status

Integratsiya:
- Pered chuvstvitelnym deystviem (hotkey/mix/workflow) mozhno zvat `/rate/limit/status`,
  a ustanovku provodit cherez `/rate/limit/set` (kontrakty vyzyvayuschikh moduley ne lomaem).

Mosty:
- Yavnyy: (Bezopasnost ↔ Veb) edinaya tochka upravleniya rate limit cherez REST.
- Skrytyy #1: (Infoteoriya ↔ Shum) limiterator ogranichivaet «chastotu» signalov, snizhaya shum.
- Skrytyy #2: (Kibernetika ↔ Kontrol) predikaty dopuska formalizuyut obratnuyu svyaz v konturakh.
- Skrytyy #3: (Memory/Audit ↔ Prozrachnost) otvety determinirovany - ikh legko logirovat.

Zemnoy abzats:
Dumay o module kak o «serdechnom voditele ritma»: zadaem verkhnyuyu chastotu udarov (zaprosov v minutu),
i sistema ne daet «fibrillirovat» servisu pod nagruzkoy.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import yadra limitera
try:
    from modules.security.rate_limiter import set_limit as _set_limit, status as _status  # type: ignore
except Exception:  # pragma: no cover
    _set_limit = _status = None  # type: ignore

bp = Blueprint("rate_limiter_routes", __name__, url_prefix="/rate/limit")


@bp.post("/set")
def set_():
    """Ustanovit limit dlya klyucha (zaprosov v minutu)."""
    if _set_limit is None:
        return jsonify({"ok": False, "error": "rate_limiter_unavailable"}), 500

    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    key = str(data.get("key", "hotkey")).strip()
    try:
        limit = int(data.get("limit_per_min", 30))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "limit_per_min must be integer"}), 400
    if not key:
        return jsonify({"ok": False, "error": "key is required"}), 400
    if limit < 0:
        return jsonify({"ok": False, "error": "limit_per_min must be >= 0"}), 400
    try:
        return jsonify(_set_limit(key, limit))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def st():
    """Zaprosit tekuschie limity/metriki."""
    if _status is None:
        return jsonify({"ok": False, "error": "rate_limiter_unavailable"}), 500
    try:
        res = _status()
        return jsonify(res if isinstance(res, dict) else {"ok": True, "status": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b