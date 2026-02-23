# -*- coding: utf-8 -*-
"""
routes/security_rbac_guard.py - before_request-gard RBAC + REST/metriki.

Endpointy:
  • GET /security/rbac/config
  • GET /metrics/rbac_guard

Mosty:
- Yavnyy: (Bezopasnost ↔ Operatsii) primenyaem RBAC bez pravok chuzhikh routov.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) vidno pravila i schetchiki deny/allow.
- Skrytyy #2: (UX ↔ Sovmestimost) myagkiy rezhim: po umolchaniyu vyklyuchen (env RBAC_ENFORCE=0).

Zemnoy abzats:
Eto «schit na vkhode»: kogda nado - vklyuchili i zaschitili kritichnye ruchki. Kogda ne nado - ne meshaem.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional, Set

from flask import Blueprint, Response, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rbac = Blueprint("rbac_guard", __name__)


# Myagkiy import yadra RBAC
try:  # pragma: no cover
    from modules.security.rbac import check as rbac_check, rules as rbac_rules, counters as rbac_counters  # type: ignore
    try:
        from modules.security.rbac import roles_from_context as _roles_from_context  # type: ignore
    except Exception:
        try:
            from modules.security.rbac import _roles_from_context as _roles_from_context  # type: ignore
        except Exception:
            _roles_from_context = None  # type: ignore
except Exception:  # pragma: no cover
    rbac_check = rbac_rules = rbac_counters = _roles_from_context = None  # type: ignore


def _rbac_enabled() -> bool:
    """RBAC vklyuchaetsya cherez RBAC_ENFORCE=1 libo flag iz schetchikov rbac_counters()."""
    if os.getenv("RBAC_ENFORCE", "0") == "1":
        return True
    try:
        if rbac_counters is not None:
            _, enabled = rbac_counters()  # type: ignore[misc]
            return bool(enabled)
    except Exception:
        pass
    return False


def register(app):  # pragma: no cover
    app.register_blueprint(bp_rbac)

    @app.before_request
    def _rbac_before_request():
        # Esli yadro RBAC nedostupno ili vyklyucheno - ne vmeshivaemsya.
        if rbac_check is None or not _rbac_enabled():
            return None

        path = request.path or ""
        # Ne sekem sami sebya i metriki
        if path.startswith("/security/rbac") or path.startswith("/metrics"):
            return None

        try:
            roles: Set[str] = _roles_from_context() if _roles_from_context else set()  # type: ignore[operator]
        except Exception:
            roles = set()

        try:
            allowed = bool(rbac_check(path, request.method, roles))
        except Exception:
            # fail-closed v rezhime RBAC
            allowed = False

        if not allowed:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "forbidden_by_rbac",
                        "path": path,
                        "method": request.method,
                        "roles": list(roles),
                    }
                ),
                403,
            )
        return None


def init_app(app):  # pragma: no cover
    register(app)


@bp_rbac.get("/security/rbac/config")
def cfg():
    """Tekuschaya konfiguratsiya i priznak vklyuchennosti RBAC."""
    try:
        rules = rbac_rules() if rbac_rules else {}
    except Exception:
        rules = {}
    enabled = _rbac_enabled()
    return jsonify({"ok": True, "enabled": enabled, "rules": rules})


@bp_rbac.get("/metrics/rbac_guard")
def metrics():
    """Prometheus-metriki RBAC-gvarda."""
    if rbac_counters is None:
        body = "rbac_enabled 0\nrbac_allowed_total 0\nrbac_denied_total 0\n"
    else:
        try:
            counters, enabled = rbac_counters()  # type: ignore[misc]
            body = (
                f"rbac_enabled {1 if enabled else 0}\n"
                f"rbac_allowed_total {counters.get('allowed_total', 0)}\n"
                f"rbac_denied_total {counters.get('denied_total', 0)}\n"
            )
        except Exception:
            body = "rbac_enabled 0\nrbac_allowed_total 0\nrbac_denied_total 0\n"

    return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


__all__ = ["bp_rbac", "register", "init_app"]
# c=a+b