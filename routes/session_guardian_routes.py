# -*- coding: utf-8 -*-
"""
routes/session_guardian_routes.py - tsentralizovannyy guard, kotoryy NE lomaet UI/avtofiks.

Chto delaet:
  • Stavit before_request-khuki cherez security.auth_rbac.install_hooks(app).
  • Daet prostuyu diagnostiku na /guard/status.
  • Uchityvaet ENV: RBAC_MODE, RBAC_AB, RBAC_EXTRA_ALLOW.

Mosty:
  • Yavnyy: (Inzheneriya bezopasnosti ↔ Ekspluatatsiya) - guard upravlyaemyy peremennymi okruzheniya.
  • Skrytyy #1: (Infoteoriya ↔ Nadezhnost) - allowlist snizhaet lozhnye srabatyvaniya i shum.
  • Skrytyy #2: (Kibernetika ↔ Refleksy) - sloty A/B dlya myagkogo vklyucheniya i avto-otkata bez dauntayma.

Zemnoy abzats:
  Ranshe globalnyy filtr mog otdavat 403 dlya sluzhebnykh ruchek i UI.
  Teper bazovyy allowlist puskaet /ui/*, /autofix/*, /debug/*, /app/discover/*
  (v slote A), a dop. puti dobavlyayutsya cherez RBAC_EXTRA_ALLOW - bez pravok koda.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Yadro RBAC: myagkiy import
try:  # pragma: no cover
    from security.auth_rbac import install_hooks, _split_extra_allow  # type: ignore
except Exception as e:  # avariynyy rezhim - ne padaem
    install_hooks = None  # type: ignore
    _split_extra_allow = None  # type: ignore
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

bp = Blueprint("session_guardian", __name__)


def _extra_allow() -> List[str]:
    """
    Vozvraschaet spisok dopolnitelnykh allow-patternov iz yadra (esli dostupno)
    libo iz peremennoy okruzheniya RBAC_EXTRA_ALLOW.
    """
    if _split_extra_allow is not None:
        try:
            return [s for s in _split_extra_allow() if s]  # type: ignore[misc]
        except Exception:
            pass
    env = os.getenv("RBAC_EXTRA_ALLOW", "")
    return [s.strip() for s in env.split(",") if s.strip()]


@bp.get("/guard/status")
def guard_status():
    """Diagnostika statusa RBAC-khukera i tekuschikh peremennykh okruzheniya."""
    info: Dict[str, Any] = {
        "ok": True,
        "rbac_mode": os.getenv("RBAC_MODE", "regex"),
        "rbac_ab": os.getenv("RBAC_AB", "A"),
        "extra_allow": _extra_allow(),
        "hooks_available": install_hooks is not None,
    }
    if _IMPORT_ERROR is not None:
        info["ok"] = False
        info["error"] = f"security.auth_rbac import failed: {_IMPORT_ERROR}"
    return jsonify(info)


def register(app):  # pragma: no cover
    """
    Drop-in tochka vkhoda (kak ranshe): registriruem blyuprint i naveshivaem khuki.
    Vazhno vyzyvat kak mozhno ranshe, chtoby politika primenyalas ko vsem marshrutam.
    """
    app.register_blueprint(bp)
    if install_hooks:
        try:
            install_hooks(app)  # type: ignore[misc]
        except Exception as e:
            try:
                app.logger.warning(f"RBAC install failed: {e}")
            except Exception:
                pass


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b