# -*- coding: utf-8 -*-
"""
routes/misrec_guard_routes.py - REST dlya misrec-guard (detektor «oshibochnykh raspoznavaniy»).

Ruchki:
  POST /misrec/set    {"window":5,"max_fails":3}
  POST /misrec/report {"success":true}
  GET  /misrec/status
  POST  /misrec/reset

Mosty:
- Yavnyy: (Vvod ↔ Kontrol) pered deystviyami proveryaem blokirovku, posle - otchityvaemsya o rezultate.
- Skrytyy #1: (Infoteoriya ↔ Ustoychivost) skolzyaschee okno snizhaet shum reaktsiy sistemy na vspleski oshibok.
- Skrytyy #2: (Kibernetika ↔ Obratnaya svyaz) /report zamykaet kontur upravleniya kachestvom.
- Skrytyy #3: (Audit ↔ Prozrachnost) interfeysnyy sloy unifitsiruet JSON-kontrakty dlya zhurnalov/alertov.

Zemnoy abzats:
Dumay o module kak o «kolennoy chashechke» - esli podryad neskolko promakhov (mis-recognition),
sistema reflektorno «prisedaet» (blocked=true), poka ne vosstanovitsya.

c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Myagkiy import yadra
try:
    from modules.vision.misrec_guard import (  # type: ignore
        set_policy as _set_policy,
        report as _report,
        status as _status,
        reset as _reset,
    )
except Exception:  # pragma: no cover
    _set_policy = _report = _status = _reset = None  # type: ignore

bp = Blueprint("misrec_guard_routes", __name__)


@bp.post("/misrec/set")
def set_():
    """Zadat parametry okna i poroga oshibok."""
    if _set_policy is None:
        return jsonify({"ok": False, "error": "misrec_guard unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        window = int(d.get("window", 5))
        max_fails = int(d.get("max_fails", 3))
        if window <= 0 or max_fails < 0:
            raise ValueError("window>0 and max_fails>=0 required")
    except (TypeError, ValueError) as e:
        return jsonify({"ok": False, "error": f"bad_input: {e}"}), 400
    try:
        return jsonify(_set_policy(window, max_fails))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/misrec/report")
def rep():
    """Soobschit rezultat operatsii (success=true/false)."""
    if _report is None:
        return jsonify({"ok": False, "error": "misrec_guard unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        success = bool(d.get("success", False))
        return jsonify(_report(success))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/misrec/status")
def st():
    """Tekuschiy status: zablokirovano li vypolnenie deystviy (blocked/ok/metrics)."""
    if _status is None:
        return jsonify({"ok": False, "error": "misrec_guard unavailable"}), 500
    try:
        res = _status()
        if isinstance(res, dict):
            return jsonify(res)
        return jsonify({"ok": True, "status": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/misrec/reset")
def rst():
    """Sbros schetchikov okna/oshibok."""
    if _reset is None:
        return jsonify({"ok": False, "error": "misrec_guard unavailable"}), 500
    try:
        return jsonify(_reset())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b