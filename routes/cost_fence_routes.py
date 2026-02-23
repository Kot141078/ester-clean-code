# -*- coding: utf-8 -*-
"""
routes/cost_fence_routes.py - REST dlya byudzhetov, raskhodov i otsenki stoimosti.

Mosty:
- Yavnyy: (Veb ↔ Ekonomika) bystryy kontrol: chtenie limitov, status i otsenka pered dorogoy operatsiey.
- Skrytyy #1: (Integratsiya ↔ Planirovschik) edinyy JSON-kontrakt dlya AutonomyForge/planirovschika.
- Skrytyy #2: (Audit ↔ Prozrachnost) tochki vkhoda dlya zhurnalirovaniya trat na storone bekenda.

Zemnoy abzats:
Chtoby ne «szhech» kartu na oblakakh i tokenakh - derzhim limity i proveryaem stoimost do zapuska.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_cost = Blueprint("cost_fence_routes", __name__)

# Myagkiy import yadra: pri otsutstvii - otdaem kontroliruemuyu oshibku
try:
    from modules.ops.cost_fence import (  # type: ignore
        limits as _limits,
        evaluate as _eval,
        status as _status,
        set_budgets as _set,
        spend as _spend,
    )
except Exception:  # pragma: no cover
    _limits = _eval = _status = _set = _spend = None  # type: ignore


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp_cost)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


@bp_cost.route("/cost/limits", methods=["GET"])
def api_limits():
    """Vozvraschaet tekuschie porogi stoimosti."""
    if _limits is None:
        return jsonify({"ok": False, "error": "cost_fence unavailable"}), 500
    try:
        return jsonify(_limits())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_cost.route("/ops/cost/status", methods=["GET"])
def api_status():
    """Vozvraschaet tekuschiy status byudzhetov i raskhodov."""
    if _status is None:
        return jsonify({"ok": False, "error": "cost_fence unavailable"}), 500
    try:
        return jsonify(_status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_cost.route("/cost/evaluate", methods=["POST"])
def api_eval():
    """Otsenivaet stoimost operatsii (kategoriya/summa)."""
    if _eval is None:
        return jsonify({"ok": False, "error": "cost_fence unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    cat = str(d.get("cat", "llm"))
    try:
        amount = float(d.get("amount", 0.0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "amount must be a number"}), 400
    try:
        return jsonify(_eval(cat, amount))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_cost.route("/ops/cost/set", methods=["POST"])
def api_set():
    """Ustanavlivaet novye znacheniya byudzhetov (probrasyvaem kontraktom yadra)."""
    if _set is None:
        return jsonify({"ok": False, "error": "cost_fence unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(_set(d))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_cost.route("/ops/cost/spend", methods=["POST"])
def api_spend():
    """Registriruet tratu sredstv."""
    if _spend is None:
        return jsonify({"ok": False, "error": "cost_fence unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    cat = str(d.get("cat", "llm"))
    try:
        amount = float(d.get("amount", 0.0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "amount must be a number"}), 400
    currency = str(d.get("currency", "EUR"))
    meta = d.get("meta") or {}
    try:
        return jsonify(_spend(cat, amount, currency, meta))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp_cost", "register", "init_app"]