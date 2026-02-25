# -*- coding: utf-8 -*-
"""routes/messaging_register_all_max.py - MAX-registrator (vse + avto-patch + konsol).

MOSTY:
- (Yavnyy) /messaging/register_all_max podklyuchaet ves stek, vklyuchaya avto-patch /proactive/dispatch i obedinennuyu panel.
- (Skrytyy #1) Povtornye vyzovy bezopasny (kak i v plus).
- (Skrytyy #2) Pozvolyaet vklyuchat/vyklyuchat avtoinferens prostym ENV, ne menyaya kod.

ZEMNOY ABZATs:
Odin vyzov - i u vas vklyucheny TG/WA, proaktivnost, pisma/golos, presety, health/metrics, panel i avto-auditoriya.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("messaging_register_all_max", __name__)

def _safe(app, reg, name, acc):
    try:
        r = reg(app)
        if r is not None:
            acc.append(name)
    except Exception as e:
        current_app.logger.warning("[REG-MAX] %s: %s", name, e, exc_info=True)

@bp.route("/messaging/register_all_max", methods=["GET"])
def register_all_max():
    # Bazovye moduli iz proshlykh paketov
    from routes.messaging_register_all_plus import register as reg_plus
    reg_plus(current_app)

    # Adding auto-patch and console
    from routes.proactive_dispatch_auto_patch import register as reg_auto
    from routes.messaging_console import register as reg_console

    added = []
    _safe(current_app, reg_auto, "dispatch_auto_patch", added)
    _safe(current_app, reg_console, "messaging_console", added)

    return jsonify({"ok": True, "registered": added})

def register(app):
    app.register_blueprint(bp)
    return bp