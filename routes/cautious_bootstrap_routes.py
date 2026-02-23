# -*- coding: utf-8 -*-
"""
routes/cautious_bootstrap_routes.py - REST wrapper for cautious policy bootstrap/merge and
advice for thinking steps. ASCII-only docstring to satisfy strict parsers.

Bridges:
- Explicit: Web <-> Ethos/Rules (seed/merge endpoints).
- Hidden #1: Thinking <-> Safety (advice endpoint before risky step).
- Hidden #2: Audit <-> Transparency (idempotent replies, easy to log).

Ground paragraph:
This is a small control panel: seed principles, merge rules, ask for advice.
No external I/O, pure in-process logic, safe for a closed box.

c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_caut_boot = Blueprint("cautious_bootstrap", __name__)

# Optional dependencies (best-effort)
try:
    from modules.policy.cautious_ethos import auto_bootstrap, seed_ethos, merge_rules  # type: ignore
    from modules.policy.cautious_freedom import evaluate  # type: ignore
except Exception:
    auto_bootstrap = seed_ethos = merge_rules = None  # type: ignore
    evaluate = None  # type: ignore

TH_AB = (os.getenv("THINKING_SAFETY_AB", "A") or "A").upper()


def register(app):
    """Idempotent blueprint registration and best-effort auto bootstrap."""
    if "cautious_bootstrap" in app.blueprints:
        return app
    app.register_blueprint(bp_caut_boot)
    try:
        if auto_bootstrap:
            auto_bootstrap()
    except Exception:
        pass
    return app


@bp_caut_boot.route("/policy/caution/seed", methods=["POST"])
def api_seed():
    if seed_ethos is None:
        return jsonify({"ok": False, "error": "cautious_ethos unavailable"}), 500
    try:
        return jsonify(seed_ethos())
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp_caut_boot.route("/policy/caution/rules", methods=["GET"])
def api_rules():
    if merge_rules is None:
        return jsonify({"ok": False, "error": "cautious_ethos unavailable"}), 500
    try:
        rep = merge_rules()
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp_caut_boot.route("/policy/caution/advice", methods=["POST"])
def api_advice():
    """
    Input:  {"path":"/route","method":"POST","body":{...}}
    Output: {"allow":bool,"level":"low|medium|high","requires_pill":bool,"tips":[...]}
    """
    if TH_AB == "B":
        return jsonify({"ok": True, "echo": True, "tips": ["A/B=B: advisory disabled"]})
    if evaluate is None:
        return jsonify({"ok": False, "error": "caution evaluator unavailable"}), 500

    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    path = str(d.get("path") or "")
    method = str(d.get("method") or "GET")
    body = d.get("body") or {}

    try:
        dec: Dict[str, Any] = evaluate(path, method, body)  # type: ignore[call-arg]
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    tips = []
    if not dec.get("allow", True):
        tips.append("Request a time-limited consent pill.")
    if dec.get("level") == "high":
        tips.extend([
            "Split the action into smaller safe steps.",
            "Ask operator confirmation via UI.",
            "Save a draft; avoid auto-run.",
        ])
    if dec.get("level") == "medium":
        tips.append("Add observation/logging and delayed rollback.")

    return jsonify({"ok": True, **dec, "tips": tips})
# c=a+b