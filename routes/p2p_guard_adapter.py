# -*- coding: utf-8 -*-
"""routes/p2p_guard_adapter.py - myagkaya "shtorka" dlya edinogo standarta P2P-podpisi.

Mosty:
- Yavnyy: (R outy v†" Dard) proverka X-P2P-Signature/X-P2P-Ts dlya /self/archives Re /p2p/* bez pravki samikh routov.
- Skrytyy #1: (Legacy v†" New) prinimaem X-P2P-Auth Re X-HMAC-Signature kak vremennuyu sovmestimost (deprecation).
- Skrytyy #2: (Stabilnost v†" Otkat) peremennaya okruzheniya P2P_GUARD_MODE=A|B (A — vklyucheno, B — vyklyucheno).

Zemnoy abzats:
Edinaya proverka na vkhode ubiraet raskhozhdeniya v zagolovkakh mezhdu raznymi klientami, no ne lomaet starye.
# c=a+b"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from flask import Blueprint, abort, jsonify, request, g, current_app, make_response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    # We use our unified verifier
    from security import p2p_signature
except Exception as e:
    p2p_signature = None  # type: ignore

bp = Blueprint("p2p_guard_adapter", __name__)

def _should_guard(path: str, method: str) -> bool:
    """Beshaem gard tochechno:
      • /self/archives - lyuboy metod (istoricheski zaschischen P2P-zagolovkami);
      • /p2p/* - minimum na POST/PUT/PATCH (replikatsiya)."""
    if not path:
        return False
    if path == "/self/archives":
        return True
    if path.startswith("/p2p/"):
        return True
    return False

def _is_enabled() -> bool:
    # A - on (by default), B - off (fast A/B rollback, if suddenly needed)
    return (os.getenv("P2P_GUARD_MODE", "A") or "A").upper() != "B"

def _secret_present() -> bool:
    # If no secret is specified, no signature is required (compatible with current behavior)
    return bool(os.getenv("ESTER_P2P_SECRET", ""))

@bp.before_app_request
def p2p_guard_before_request():
    """Dlobalnaya (no tochechnaya) proverka podpisi pered vyzovom routov.
    Ne menyaet suschestvuyuschie kontrakty - tolko 401 na otsutstvie/nevalidnost podpisi pri vklyuchennom sekrete."""
    if not _is_enabled():
        return None  # mode B - guard off
    if p2p_signature is None:
        return None  # library is not available - file is open (as it was)
    if not _secret_present():
        return None  # sekreta net — podpis neobyazatelna

    path = request.path or ""
    method = request.method or "GET"
    if not _should_guard(path, method):
        return None

    # Verifikatsiya
    body = request.get_data(cache=True) or b""
    err = p2p_signature.verify_any(
        headers=request.headers,
        method=method,
        path=path,
        body=body,
    )
    if err is None:
        # Remember, if the client used legacy aliases, we’ll set the depresation header in the after_request
        used_legacy = False
        if request.headers.get("X-P2P-Auth") or request.headers.get("X-HMAC-Signature"):
            used_legacy = True
        g._p2p_used_legacy = used_legacy  # type: ignore[attr-defined]
        return None

    # Verification error in single response 401
    resp = jsonify({"ok": False, "error": err})
    return abort(make_response(resp, 401))

@bp.after_app_request
def p2p_guard_after_request(response):
    """On successful requests, we add a soft hint about the gradual cancellation of legacy headers."""
    try:
        if getattr(g, "_p2p_used_legacy", False):
            response.headers["X-P2P-Deprecation"] = "legacy"
    except Exception:
        pass
    return response




def register(app):
    app.register_blueprint(bp)
    return app
