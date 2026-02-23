# -*- coding: utf-8 -*-
"""
routes/self_capabilities_routes.py - REST: karta vozmozhnostey, bazovyy self-check i metriki + prostoy UI.

Endpointy:
  • GET  /self/capabilities
  • GET  /self/health
  • GET  /metrics/self_capabilities
  • GET  /admin/self   - HTML-panel operatora (shablon v templates/self_console.html)

Mosty:
- Yavnyy: (Volya ↔ Samopoznanie) agent i operator vidyat, chem sistema realno raspolagaet.
- Skrytyy #1: (Inzheneriya ↔ Podderzhka) karta routov pomogaet izbezhat konflikta putey.
- Skrytyy #2: (Audit ↔ Nadezhnost) metriki snapshotov vidny v Prometheus.

Zemnoy abzats:
Eto pribornaya panel: spisok rychagov/knopok i indikator «zdorovya» - mozhno prinimat resheniya.

# c=a+b
"""
from __future__ import annotations

import os, platform, sys
from typing import Any, Dict
from flask import Blueprint, jsonify, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_self_caps = Blueprint("self_caps", __name__, template_folder="../templates", static_folder="../static")

try:
    from modules.self.capability_registry import snapshot, counters  # type: ignore
except Exception:
    snapshot = counters = None  # type: ignore

_CNT = {"health_calls": 0}

def register(app):
    app.register_blueprint(bp_self_caps)

@bp_self_caps.route("/self/capabilities", methods=["GET"])
def api_caps():
    if snapshot is None:
        return jsonify({"ok": False, "error": "capability_registry unavailable"}), 500
    return jsonify({"ok": True, "caps": snapshot()})

@bp_self_caps.route("/self/health", methods=["GET"])
def api_health():
    _CNT["health_calls"] += 1
    rep = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "env_flags": {
            "SELF_CAPS_AB": os.getenv("SELF_CAPS_AB","A"),
            "SELF_PLAN_AB": os.getenv("SELF_PLAN_AB","A"),
            "SELF_CODE_AB": os.getenv("SELF_CODE_AB","A"),
        }
    }
    # bystraya proverka klyuchevykh podsistem (best-effort)
    try:
        import flask  # noqa
        rep["flask_ok"] = True
    except Exception:
        rep["flask_ok"] = False
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        rep["actions_seen"] = len(list_actions())
    except Exception:
        rep["actions_seen"] = 0
    return jsonify({"ok": True, "health": rep})

@bp_self_caps.route("/metrics/self_capabilities", methods=["GET"])
def metrics():
    c = counters()() if callable(counters) else {}
    return (f"self_caps_snapshots_total {c.get('snapshots_total',0)}\n"
            f"self_caps_health_calls {_CNT['health_calls']}\n",
            200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})

@bp_self_caps.route("/admin/self", methods=["GET"])
def admin_self():
    return render_template("self_console.html")