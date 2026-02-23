# -*- coding: utf-8 -*-
"""
routes/self_forge_guarded_routes.py - guarded apply: dry-run -> apply -> health -> auto-rollback.

Bridges:
- Explicit: Cybernetics <-> Reliability (only keep changes if health stays OK).
- Hidden #1: CautionNet <-> Consent (requires explicit call, can be surrounded by policy).
- Hidden #2: Audit <-> Ledger (returns plan/result suitable for external logging).

Ground paragraph:
It is a careful change switch. If health probe fails after apply, roll back paths
that were changed. All operations are in-process and do not require network I/O.

c=a+b
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_forge_guard = Blueprint("self_forge_guarded", __name__)

# Optional dependencies
try:
    from modules.self.forge import dry_run as _dry, apply as _apply  # type: ignore
    from modules.resilience.health import check as _health  # type: ignore
    from modules.resilience.rollback import rollback_paths as _rb  # type: ignore
except Exception:
    _dry = _apply = _health = _rb = None  # type: ignore

FORGE_T = int(os.getenv("FORGE_HEALTH_TIMEOUT_SEC", "10") or "10")


def register(app):
    """Idempotent blueprint registration."""
    if "self_forge_guarded" in app.blueprints:
        return app
    app.register_blueprint(bp_forge_guard)
    return app


@bp_forge_guard.route("/self/forge/guarded_apply", methods=["POST"])
def api_guarded():
    if None in (_dry, _apply, _health, _rb):
        return jsonify({"ok": False, "error": "guard_unavailable"}), 500

    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ch: List[Dict[str, Any]] = list(d.get("changes") or [])

    # dry-run
    try:
        plan: Dict[str, Any] = (_dry(ch) or {})  # type: ignore[call-arg]
    except Exception as e:
        return jsonify({"ok": False, "error": f"dry_run_failed: {e}"}), 500
    if not isinstance(plan, dict) or not plan.get("ok", False):
        return jsonify({"ok": False, "error": "dry_run_failed", "plan": plan}), 400

    # apply
    try:
        res: Dict[str, Any] = (_apply(ch) or {})  # type: ignore[call-arg]
    except Exception as e:
        return jsonify({"ok": False, "error": f"apply_failed: {e}", "plan": plan}), 500
    if not isinstance(res, dict) or not res.get("ok", False):
        return jsonify({"ok": False, "error": "apply_failed", "apply": res, "plan": plan}), 500

    # health probe
    t0 = time.time()
    ok = False
    probe: Dict[str, Any] = {}
    while time.time() - t0 < FORGE_T:
        try:
            probe = _health() or {}  # type: ignore[misc]
        except Exception:
            probe = {}
        if isinstance(probe, dict) and probe.get("ok"):
            ok = True
            break
        time.sleep(1.0)

    if ok:
        return jsonify({"ok": True, "plan": plan, "apply": res, "health": probe})

    # rollback
    paths = [x.get("path") for x in ch if isinstance(x, dict) and x.get("path")]
    try:
        rb = _rb(paths)  # type: ignore[misc]
    except Exception as e:
        rb = {"ok": False, "error": f"rollback_failed: {e}"}

    return jsonify(
        {
            "ok": False,
            "error": "health_failed_after_apply",
            "plan": plan,
            "apply": res,
            "health": probe,
            "rollback": rb,
        }
    )
# c=a+b