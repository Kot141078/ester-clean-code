# -*- coding: utf-8 -*-
"""routes/kg_routes.py - REST: /mem/kg/autolink

Mosty:
- Yavnyy: (Veb ↔ KG) bystryy avtolink suschnostey dlya dokumentov/subtitrov/zametok.
- Skrytyy #1: (Profile ↔ Prozrachnost) zhurnaliruem result.
- Skrytyy #2: (RAG ↔ Podsvetka) uzly prigodyatsya dlya navigatsii/podskazok.

Zemnoy abzats:
Paket iz tekstov na vkhod - svyazi “dokument→suschnost” na vykhode. Prostoy sposob ozhivit graf znaniy.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("kg_routes", __name__)


def register(app):  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    register(app)


# Soft kernel import
try:
    from modules.kg.autolink import autolink as _autolink  # type: ignore
except Exception:  # pragma: no cover
    _autolink = None  # type: ignore


def _log_passport(event: str, data: Dict[str, Any]) -> None:
    """Journaling in a memory “profile” (best-effort)."""
    try:
        from modules.mem.passport import append as passport  # type: ignore
        passport(event, data, "kg://routes")
    except Exception:
        pass


@bp.route("/mem/kg/autolink", methods=["POST"])
def api_autolink():
    if _autolink is None:
        return jsonify({"ok": False, "error": "kg_unavailable"}), 500

    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    items: List[Dict[str, Any]] = list(d.get("items") or [])
    options: Optional[Dict[str, Any]] = d.get("options") if isinstance(d.get("options"), dict) else None

    if not items:
        return jsonify({"ok": False, "error": "items required (list)"}), 400

    try:
        try:
            rep = _autolink(items, options=options)  # type: ignore[call-arg]
        except TypeError:
            # Starye signatury bez options
            rep = _autolink(items)  # type: ignore[misc]
    except Exception as e:
        _log_passport("kg_autolink_fail", {"n": len(items), "error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500

    if isinstance(rep, dict):
        _log_passport("kg_autolink", {"n": len(items), "ok": bool(rep.get("ok", True))})
        return jsonify(rep)

    # Compatibility if the module returned a non-dictionary
    out = {"ok": True, "items": rep}
    _log_passport("kg_autolink", {"n": len(items), "ok": True})
    return jsonify(out)


__all__ = ["bp", "register", "init_app"]
# c=a+b