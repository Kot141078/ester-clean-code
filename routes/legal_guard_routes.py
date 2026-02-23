# -*- coding: utf-8 -*-
"""
routes/legal_guard_routes.py - REST: /policy/legal/check

Mosty:
- Yavnyy: (Veb ↔ Politika) tochka proverki zadach i planov.
- Skrytyy #1: (Volya ↔ Ostorozhnost) legko vstraivaetsya v thinking_pipeline.
- Skrytyy #2: (Zhurnaly ↔ Audit) pri zhelanii dobavlyaetsya zapis «profileom».
- Skrytyy #3: (Logika ↔ Kontrakty) strogiy JSON-kontrakt oblegchaet formalnuyu proverku.

Zemnoy abzats:
Pered tem kak delat - sprosili yurista. Bystro, ponyatno i bez syurprizov.

c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("legal_guard_routes", __name__)


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)


# Myagkiy import yadra (ispravleno: tochechnyy import vmesto slesha)
try:
    from modules.policy.legal_guard import check as _check  # type: ignore
except Exception:  # pragma: no cover
    _check = None  # type: ignore


def _log_passport(event: str, data: Dict[str, Any]) -> None:
    """Optsionalnyy audit v «profile» pamyati (best-effort)."""
    try:
        from modules.mem.passport import append as passport  # type: ignore
        passport(event, data, "policy://legal_guard")
    except Exception:
        pass


@bp.route("/policy/legal/check", methods=["POST"])
def api_check():
    """
    Vkhod (JSON):
      { "task": {..} | "plan": {..} | "text": "..." }
    Vykhod: proxied otvet modulya legal_guard.check(...)
    """
    if _check is None:
        return jsonify({"ok": False, "error": "legal_guard_unavailable"}), 500

    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    payload: Dict[str, Any] = {}

    # Normalizatsiya vkhoda: dopuskaem task/plan/text, stroki i obekty
    if "task" in data:
        payload["task"] = data["task"]
    if "plan" in data:
        payload["plan"] = data["plan"]
    if "text" in data and data.get("text"):
        payload["text"] = str(data["text"])

    if not payload:
        # Follbek: esli prishel prosto tekst bez klyucha
        txt = data.get("q") or data.get("input")
        if txt:
            payload["text"] = str(txt)

    if not payload:
        return jsonify({"ok": False, "error": "empty payload"}), 400

    try:
        res = _check(payload)  # type: ignore[misc]
        if isinstance(res, dict):
            _log_passport("legal_check", {"ok": bool(res.get("ok", True))})
            return jsonify(res)
        # Sovmestimost: esli modul vernul ne-slovar
        out = {"ok": True, "result": res}
        _log_passport("legal_check", {"ok": True})
        return jsonify(out)
    except Exception as e:
        _log_passport("legal_check_fail", {"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp", "register", "init_app"]
# c=a+b