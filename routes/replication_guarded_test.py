# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/replication_guarded_test.py - zaschischennye testovye ruchki replikatsii (mTLS + rol "replicator").

Marshruty:
  GET  /replication/test_snapshot  -> {"ok":true,"type":"snapshot","items":0}
  POST /replication/test_apply     -> {"ok":true,"type":"apply","got":{...}}

Mosty:
- Yavnyy: (Bezopasnost ↔ Replikatsiya) dostup k testovym ruchkam tolko pri roli «replicator».
- Skrytyy #1: (Logika ↔ Kontrakty) strogiy JSON-otvet i kody 200/403 dlya avtomatizirovannykh smoke-testov.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) «myagkiy» import rolemap - modul ne padaet pri otsutstvii mappera.

Zemnoy abzats:
Eto «kontrolnyy turniket» na vkhod v kontur replikatsii: ingress kladet zagolovki mTLS,
my sveryaem rol i tolko potom pozvolyaem vypolnyat operatsii (pust i testovye).

c=a+b
"""

from typing import Optional, Callable, Any
from functools import wraps

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Not a pytest module despite its historical filename.
__test__ = False

# Myagkiy import role-map: pri otsutstvii vozvraschaem None (dostup budet zapreschen)
try:
    from security.mtls_rolemap import map_dn_to_role  # type: ignore
except Exception:  # pragma: no cover
    map_dn_to_role = None  # type: ignore

bp = Blueprint("replication_guarded", __name__, url_prefix="/replication")


def _mtls_role_from_headers() -> Optional[str]:
    """Sovmestimo s ingress, prokidyvayuschim zagolovki pri uspeshnom mTLS."""
    if (request.headers.get("X-Client-Verified") or "").upper() != "SUCCESS":
        return None
    dn = request.headers.get("X-Client-DN", "") or ""
    return map_dn_to_role(dn) if map_dn_to_role else None


def _require_roles(roles: list[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Dekorator dopuska tolko dlya spiska roley (403 pri nesootvetstvii)."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*a: Any, **kw: Any):
            role = _mtls_role_from_headers()
            if role is None or role not in roles:
                return jsonify({"ok": False, "error": "mtls_forbidden", "need": roles, "role": role}), 403
            return fn(*a, **kw)
        return wrapper
    return decorator


@bp.get("/test_snapshot")
@_require_roles(["replicator"])
def replication_test_snapshot():
    """Zaschischennaya ruchka: razreshena tolko roli 'replicator'. Vozvraschaet fiktivnyy «snepshot»."""
    return jsonify({"ok": True, "type": "snapshot", "items": 0})


@bp.post("/test_apply")
@_require_roles(["replicator"])
def replication_test_apply():
    """Primenenie «snepshota» (testovoe). Prinimaet proizvolnyy JSON i vozvraschaet ego v otvete."""
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}
    return jsonify({"ok": True, "type": "apply", "got": payload})


def register_replication_guarded(app) -> None:  # pragma: no cover
    """Istoricheskaya sovmestimaya registratsiya blyuprinta (imya iz dampa)."""
    app.register_blueprint(bp)


# Unifitsirovannye khuki proekta
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(bp)


__all__ = ["bp", "register_replication_guarded", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app
