# -*- coding: utf-8 -*-
from __future__ import annotations

"""routes/ops_mtls_guarded.py - mTLS-zaschita OPS-endpointov.

Resource:
  GET /ops/secure_ping - dostupen only mTLS→role=="ops"

Mosty:
- Yavnyy: (Bezopasnost ↔ Operatsii) prostaya proverka roli “ops” cherez zagolovki ot ingress.
- Skrytyy #1: (Logika ↔ Kontrakty) determinirovannye JSON-kody 403/200 dlya avtomatov.
- Skrytyy #2: (Audit ↔ Prozrachnost) rol vychislyaetsya cherez map_dn_to_role (pravila v repo).

Zemnoy abzats:
Eto “turniket dlya tekhnikov”: ingress kladet v zagolovki rezultat mTLS i DN, my po kartam dostupa
opredelyaem, puskat li cheloveka na ploschadku “ops”.

# c=a+b"""

from typing import Optional, Callable, Any
from functools import wraps

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Soft import of role mapper: if missing, there is no role (access = 403)
try:
    from security.mtls_rolemap import map_dn_to_role  # type: ignore
except Exception:  # pragma: no cover
    map_dn_to_role = None  # type: ignore

bp_ops_guard = Blueprint("ops_mtls_guarded", __name__, url_prefix="/ops")


def _mtls_role_from_headers() -> Optional[str]:
    """Returns the user's role from the mTLS or None headers."""
    if (request.headers.get("X-Client-Verified") or "").upper() != "SUCCESS":
        return None
    dn = request.headers.get("X-Client-DN", "") or ""
    return map_dn_to_role(dn) if map_dn_to_role else None


def _require_ops_role() -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Tolerance decorator for role hops only (403 if mismatched)."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*a: Any, **kw: Any):
            role = _mtls_role_from_headers()
            if role != "ops":
                return (
                    jsonify({"ok": False, "error": "mtls_forbidden", "need": ["ops"], "role": role}),
                    403,
                )
            return fn(*a, **kw)
        return wrapper
    return decorator


@bp_ops_guard.get("/secure_ping")
@_require_ops_role()
def secure_ping():
    return jsonify({"ok": True, "scope": "ops", "path": request.path})


def register_ops_mtls_guarded(app) -> None:  # pragma: no cover
    """Historical registration name from dump."""
    app.register_blueprint(bp_ops_guard)


# Unified project hooks
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp_ops_guard)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(bp_ops_guard)


__all__ = ["bp_ops_guard", "register_ops_mtls_guarded", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp_ops_guard)
    return app