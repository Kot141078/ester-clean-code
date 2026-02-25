# -*- coding: utf-8 -*-
"""routes/autonomy_routes.py - Edinyy REST-interfeys dlya upravleniya avtonomiey, planirovaniya i ispolneniya.

Mosty:
- Yavnyy: (Veb ↔ Avtonomiya) tseli → plan → ispolnenie.
- Skrytyy #1: (Ekonomika/Set ↔ Politiki) kontrol byudzhetov i porogov na urovne policy.*.
- Skrytyy #2: (Integratsiya ↔ Deystviya) rabotaet poverkh action_registry i guard'ov.

Endpoint (JWT):
  POST /autonomy/start - zapustit fonovogo vorkera
  POST /autonomy/stop - ostanovit vorkera
  POST /autonomy/tick - odin tsikl obrabotki sobytiy (limit?)
  POST /autonomy/install - postavit RRULE dlya autonomy:tick
  GET /autonomy/status - status (policy.*)
  POST /autonomy/level - uroven svobody (0..3) dlya policy.LEVEL
  GET /autonomy/ledger?limit=N - khvost zhurnala resolution
  POST /autonomy/plan - sformirovat plan na osnove tseli/byudzheta/tseley
  POST /autonomy/act - vypolnit plan
  --- state API ---
  POST /autonomy/scope - ogranichit zony (rpa_ui/network/files/dialog/game) + ttl
  POST /autonomy/pause - pauza on/off
  POST /autonomy/revoke - otozvat vse razresheniya
  POST /autonomy/check - proverit soglasie/uroven (will.consent_gate)
  GET /autonomy/state - sostoyanie iz modules.autonomy.state.get()"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, request, render_template
from flask_jwt_extended import jwt_required  # type: ignore

# Imports for lifecycle management and policies
from modules.scheduler_engine import create_task  # type: ignore
from modules.autonomy_bridge import start_background, stop_background, consume_once  # type: ignore
from modules import decision_policy as policy  # type: ignore

# Imports for state API
from modules.autonomy.state import set_level as state_set_level, set_scope, pause, revoke, get as state_get  # type: ignore
from modules.will.consent_gate import check as will_check  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Imports for planning/execution (soft dependency)
try:
    from modules.self.autonomy import plan as _plan, act as _act  # type: ignore
except Exception:  # pragma: no cover
    _plan = _act = None  # type: ignore

bp = Blueprint("autonomy_routes", __name__, url_prefix="/autonomy")


# --- Upravlenie vorkerom ---
@bp.post("/start")
@jwt_required()
def autonomy_start():
    """Starts the autonomy background worker."""
    ok = start_background()
    return jsonify({"ok": bool(ok)})


@bp.post("/stop")
@jwt_required()
def autonomy_stop():
    """Ostanavlivaet fonovogo vorkera avtonomii."""
    try:
        stop_background()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/tick")
@jwt_required()
def autonomy_tick():
    """Runs one event loop (consume_once)."""
    try:
        limit = int((request.get_json(silent=True) or {}).get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200
    try:
        report = consume_once(limit=limit)
        return jsonify(report)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/install")
@jwt_required()
def autonomy_install():
    """Sets up a periodic task to call tick on GRULE."""
    try:
        rrule = "RRULE:FREQ=MINUTELY;INTERVAL=1"
        payload = {"kind": "autonomy:tick", "payload": {"source": "autonomy_routes"}}
        res = create_task("autonomy_tick", "publish_event", rrule, payload)
        return jsonify({"ok": True, "task": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Konfiguratsiya/status policy.* ---
@bp.get("/status")
@jwt_required()
def autonomy_status():
    """Returns the current police autonomy settings (level, thresholds, quiet hours)."""
    return jsonify(
        {
            "ok": True,
            "level": getattr(policy, "LEVEL", None),
            "thresholds": {
                "max_risk": getattr(policy, "MAX_RISK", None),
                "min_conf": getattr(policy, "MIN_CONF", None),
            },
            "quiet": {
                "start": getattr(policy, "QUIET_START", None),
                "end": getattr(policy, "QUIET_END", None),
            },
        }
    )


@bp.post("/level")
@jwt_required()
def autonomy_level():
    """Ustanavlivaet uroven avtonomii policy.LEVEL (0-3)."""
    data = request.get_json(silent=True) or {}
    level = data.get("level")
    try:
        level_int = int(level)
    except Exception:
        return jsonify({"ok": False, "error": "level must be an integer 0..3"}), 400
    if level_int not in (0, 1, 2, 3):
        return jsonify({"ok": False, "error": "level must be an integer 0..3"}), 400

    os.environ["AUTONOMY_LEVEL"] = str(level_int)
    try:
        policy.LEVEL = level_int  # type: ignore[attr-defined]
    except Exception:
        pass
    return jsonify({"ok": True, "level": level_int})


@bp.get("/ledger")
@jwt_required()
def autonomy_ledger():
    """Tail of autonomy decision log (police.ed_ledger_tail)."""
    try:
        limit = int(request.args.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    tail = getattr(policy, "read_ledger_tail", lambda **_: [])(limit=limit)
    return jsonify({"ok": True, "items": tail})


# --- Planirovanie i ispolnenie ---
@bp.post("/plan")
@jwt_required()
def api_plan():
    """Accepts a goal/budget/target and returns an action plan."""
    if _plan is None:
        return jsonify({"ok": False, "error": "autonomy planning unavailable"}), 503
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(_plan(str(d.get("goal", "")), d.get("budget"), d.get("targets")))


@bp.post("/act")
@jwt_required()
def api_act():
    """Prinimaet plan i vypolnyaet ego."""
    if _act is None:
        return jsonify({"ok": False, "error": "autonomy acting unavailable"}), 503
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(_act(d.get("plan") or {}))


# --- Nizkourovnevyy state-API ---
@bp.post("/scope")
@jwt_required()
def scope():
    d = request.get_json(force=True, silent=True) or {}
    ttl = d.get("ttl")
    sc = {k: d.get(k) for k in ("rpa_ui", "network", "files", "dialog", "game") if k in d}
    return jsonify(set_scope(sc, ttl))


@bp.post("/pause")
@jwt_required()
def pause_():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(pause(bool(d.get("on", False))))


@bp.post("/revoke")
@jwt_required()
def revoke_():
    return jsonify(revoke())


@bp.post("/check")
@jwt_required()
def check_():
    d = request.get_json(force=True, silent=True) or {}
    need = list(d.get("need") or [])
    min_level = int(d.get("min_level", 1))
    return jsonify(will_check(need, min_level))


@bp.get("/state")
@jwt_required()
def state_status():
    """Sostoyanie iz modules.autonomy.state.get()."""
    try:
        return jsonify(state_get())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Admin-stranitsa ---
@bp.get("/admin")
@jwt_required()
def admin():
    return render_template("admin_autonomy.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint (project contract)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]