# -*- coding: utf-8 -*-
"""
routes/subconscious_routes.py — prostye ruchki upravleniya podsoznaniem.
Zavisit ot Flask-prilozheniya osnovnogo app.py (kanon Ester_dump_part_0001).
Podklyuchite blueprint v app.py.

Primer integratsii v app.py:

    from routes.subconscious_routes import bp_subcon
    app.register_blueprint(bp_subcon)
"""

import json
import os
import time
import uuid

from flask import Blueprint, jsonify, request

from modules.subconscious.engine import MEM_PATH, DreamMemory, _emit as emit_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_subcon = Blueprint("subconscious", __name__, url_prefix="/subconscious")


@bp_subcon.get("/status")
def status():
    mem = DreamMemory(MEM_PATH)
    active = mem.get_active()
    return jsonify(
        {
            "ok": True,
            "active_dreams": len(active),
            "dreams": active[:5],  # prevyu
        }
    )


@bp_subcon.post("/poke")
def poke():
    """R uchnoy «tik sna» bez planirovschika."""
    corr = uuid.uuid4().hex
    emit_event(
        "scheduler.fired",
        {
            "kind": "dream_tick",
            "origin": "manual_poke",
        },
        correlation_id=corr,
    )
    return jsonify({"ok": True, "fired": "dream_tick", "correlation_id": corr})


@bp_subcon.post("/reflect")
def reflect():
    """Prinuditelno svyazat posledniy son s prichino-sobytiem (dlya testov)."""
    mem = DreamMemory(MEM_PATH)
    act = mem.get_active()
    if not act:
        return jsonify({"ok": False, "error": "no_active_dreams"}), 400
    last = act[0]
    corr = uuid.uuid4().hex
    emit_event(
        "thinking.hypothesis",
        {
            "from_dream": {
                "title": last["title"],
                "tags": last["tags"],
                "keys": last["keys"],
                "priority": last["priority"],
                "fingerprint": last["fingerprint"],
            },
            "event": {"type": "manual.reflect", "payload": {}},
            "score": 1.0,
            "suggestion": "R uchnaya proverka svyaznosti sna Re mysli.",
        },
        correlation_id=corr,
    )
# return jsonify({"ok": True, "correlation_id": corr})


def register(app):
    app.register_blueprint(bp_subcon)
    return app