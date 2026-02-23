# -*- coding: utf-8 -*-
"""
routes/thinking_actions_routes.py — REST API dlya upravleniya Re vyzova deystviy myshleniya.

Endpointy:
  • GET  /thinking/actions/registry    - Spisok zaregistrirovannykh deystviy.
  • GET  /thinking/actions/stats       - Statistika po ispolzovaniyu slotov.
  • POST /thinking/actions/register    - R egistratsiya novogo tipa deystviya.
    {"kind","endpoint","timeout_ms"?, "concurrency"?}
  • POST /thinking/actions/begin       - Zakhvat slota dlya vypolneniya deystviya.
    {"kind"}
  • POST /thinking/actions/finish      - Osvobozhdenie slota posle vypolneniya.
    {"kind"}
  • POST /thinking/act                 - Bezopasnyy vyzov deystviya.
    {"name", "args"}

Mosty:
- Yavnyy: (Beb/Myshlenie v†" Kontrol) tsentralizovannoe Re bezopasnoe upravlenie deystviyami.
- Skrytyy #1: (Audit v†" Nadezhnost) audiruem vyzovy, zaschischaya sistemu ot peregruzok.
- Skrytyy #2: (Politiki/UX v†" Prozrachnost) edinaya tochka dlya kvot, roley Re statusov.

Zemnoy abzats:
Eto edinyy pult dlya vsekh «knopok»: registriruet, pokazyvaet, kto rabotaet i skolko slotov ostalos, i pozvolyaet bezopasno nazhat na lyubuyu iz nikh.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking_actions_routes", __name__)

try:
    # Funktsii iz modulya reestra deystviy
    from modules.thinking.action_registry import register as _reg, list_actions, begin as _begin, finish as _finish  # type: ignore
    # Funktsii iz modulya ispolnitelya deystviy
    from modules.thinking.action_invoker import stats as _stats, invoke as _invoke  # type: ignore
except Exception:
    _reg = list_actions = _begin = _finish = None  # type: ignore
    _stats = _invoke = None  # type: ignore

def register(app):
    """R egistriruet blueprint v prilozhenii Flask."""
    app.register_blueprint(bp)

@bp.route("/thinking/actions/registry", methods=["GET"])
def api_list_registry():
    """Vozvraschaet spisok vsekh zaregistrirovannykh deystviy."""
    if list_actions is None:
        return jsonify({"ok": False, "error": "actions registry unavailable"}), 500
    return jsonify({"ok": True, "actions": list_actions()})

@bp.route("/thinking/actions/stats", methods=["GET"])
def api_stats():
    """Vozvraschaet statistiku po vypolnyaemym deystviyam."""
    if _stats is None:
        return jsonify({"ok": False, "error": "invoker unavailable"}), 500
    return jsonify(_stats())

@bp.route("/thinking/actions/register", methods=["POST"])
def api_register():
    """R egistriruet novyy tip deystviya v sisteme."""
    if _reg is None:
        return jsonify({"ok": False, "error": "actions registry unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(_reg(
        kind=str(data.get("kind")),
        endpoint=str(data.get("endpoint")),
        timeout_ms=int(data.get("timeout_ms") or 30000),
        concurrency=int(data.get("concurrency") or 1)
    ))

@bp.route("/thinking/actions/begin", methods=["POST"])
def api_begin():
    """Signaliziruet o nachale vypolneniya deystviya i zakhvatyvaet slot."""
    if _begin is None:
        return jsonify({"ok": False, "error": "actions registry unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(_begin(str(data.get("kind"))))

@bp.route("/thinking/actions/finish", methods=["POST"])
def api_finish():
    """Signaliziruet o zavershenii deystviya i osvobozhdaet slot."""
    if _finish is None:
        return jsonify({"ok": False, "error": "actions registry unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    return jsonify(_finish(str(data.get("kind"))))

@bp.route("/thinking/act", methods=["POST"])
def api_act():
    """Vyzyvaet (ispolnyaet) konkretnoe deystvie s peredannymi argumentami."""
    if _invoke is None:
        return jsonify({"ok": False, "error": "invoker unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
# return jsonify(_invoke(str(d.get("name", "")), dict(d.get("args") or {})))