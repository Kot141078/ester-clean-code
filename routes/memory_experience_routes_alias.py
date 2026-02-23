# path: routes/memory_experience_routes_alias.py
# -*- coding: utf-8 -*-
"""
Unifitsirovannaya HTTP-ruchka dlya dostupa k profilyu opyta Ester.

GET /memory/experience/profile

Vozvraschaet:
    {
        "ok": bool,
        "profile": {
            "ok": bool,
            "slot": "A" | "B",
            "total_insights": int,
            "top_terms": [str],
            "sample": [{"title": str, "text": str}, ...],
            "error": str?  # esli ok == False
        }
    }
"""
from __future__ import annotations

from typing import Any, Dict
import logging

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

bp = Blueprint("memory_experience_routes_alias", __name__)


def _build_payload() -> Dict[str, Any]:
    try:
        from modules.memory import experience as experience_mod  # type: ignore
    except Exception as e:  # pragma: no cover
        log.warning(
            "memory_experience_routes_alias: cannot import modules.memory.experience: %s",
            e,
        )
        return {
            "ok": False,
            "error": "experience_module_unavailable",
            "profile": {
                "ok": False,
                "slot": "A",
                "total_insights": 0,
                "top_terms": [],
                "sample": [],
                "error": "experience_module_unavailable",
            },
        }

    get_fn = getattr(experience_mod, "get_experience_profile", None)
    build_fn = getattr(experience_mod, "build_experience_profile", None)

    if callable(get_fn):
        profile = get_fn()
    elif callable(build_fn):
        profile = build_fn()
    else:
        return {
            "ok": False,
            "error": "experience_profile_not_implemented",
            "profile": {
                "ok": False,
                "slot": "A",
                "total_insights": 0,
                "top_terms": [],
                "sample": [],
                "error": "experience_profile_not_implemented",
            },
        }

    if not isinstance(profile, dict):
        return {
            "ok": False,
            "error": "invalid_profile_format",
            "profile": {
                "ok": False,
                "slot": "A",
                "total_insights": 0,
                "top_terms": [],
                "sample": [],
                "error": "invalid_profile_format",
            },
        }

    ok = bool(profile.get("ok"))
    return {"ok": ok, "profile": profile}


@bp.route("/memory/experience/profile", methods=["GET"])
def memory_experience_profile() -> Any:
    """
    Glavnaya ruchka dlya chteniya profilya opyta.
    """
    payload = _build_payload()
    # Status vsegda 200; detali v polyakh ok/error.
    return jsonify(payload), 200


def setup(app) -> None:
    """
    Registratsiya blueprint; vyzyvaetsya iz app.py/extra_routes.
    """
    app.register_blueprint(bp)


# Obratnaya sovmestimost s raznymi zagruzchikami:
init_app = setup
register = setup
register_app = setup

__all__ = ["bp", "memory_experience_profile", "setup", "init_app", "register", "register_app"]