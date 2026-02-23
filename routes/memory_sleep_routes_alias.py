# -*- coding: utf-8 -*-
"""
routes/memory_sleep_routes_alias.py - REST-aliasy dlya sutochnogo tsikla pamyati.

Marshruty:
  GET  /memory/sleep/status        -> modules.memory.sleep_alias.status()
  POST /memory/sleep/run_now       -> modules.memory.sleep_alias.run_cycle()
  POST /memory/sleep/slot          -> modules.memory.sleep_alias.switch_slot(slot)

Kontrakty podobrany tak, chtoby ne lomat suschestvuyuschiy API: eto novye ruchki,
oni ne podmenyayut /memory/* i ne trogayut kaskad myshleniya.

MOSTY:
  • Yavnyy: Admin/UI ↔ sleep_alias ↔ daily_cycle.
  • Skrytyy #1: Avtonomnye planirovschiki ↔ HTTP (health-cheki sna).
  • Skrytyy #2: Nightly-tsikl ↔ bekapy/QA/summary/meta vnutri pamyati.

ZEMNOY ABZATs:
S tochki zreniya ekspluatatsii — esche odin "service endpoint": mozhno schelknut
curl'om i proverit, chto u Ester rabotaet noch: chistka, bekap, daydzhest.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from modules.memory import sleep_alias  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("memory_sleep_routes_alias", __name__)


@bp.get("/memory/sleep/status")
def sleep_status():
    return jsonify(sleep_alias.status())


@bp.post("/memory/sleep/run_now")
def sleep_run_now():
    return jsonify(sleep_alias.run_cycle())


@bp.post("/memory/sleep/slot")
def sleep_switch_slot():
    d = request.get_json(silent=True) or {}
    slot = d.get("slot", "")
    return jsonify(sleep_alias.switch_slot(slot))


def register(app):
    # Bezopasnaya registratsiya: esli blueprint uzhe est — ne dubliruem.
    name = bp.name
    if name not in app.blueprints:
        app.register_blueprint(bp)
    return app