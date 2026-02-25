# -*- coding: utf-8 -*-
"""routes/messaging_register_all_plus.py - “vklyuchit vse” (+ health, metrics, will-hook).

MOSTY:
- (Yavnyy) /messaging/register_all_plus registriruet TG/WA/Proactive/Presets/Mail/Health/Metrics/Adminki.
- (Skrytyy #1) Bezopasnaya registratsiya: povtornye vyzovy ne lomayut kartu marshrutov.
- (Skrytyy #2) Gotovnost k poetapnomu vklyucheniyu (mozhno vyzyvat poverkh starogo register_all).

ZEMNOY ABZATs:
Odna knopka dlya polnogo vklyucheniya kanalnoy podsistemy Ester - bez pravok app.py.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("messaging_register_all_plus", __name__)

def _safe_reg(app, reg, name, added):
    try:
        r = reg(app)
        if r is not None:
            added.append(name)
    except Exception as e:
        current_app.logger.warning("[REG+] %s: %s", name, e, exc_info=True)

@bp.route("/messaging/register_all_plus", methods=["GET"])
def register_all_plus():
    from routes.whatsapp_webhook_routes import register as reg_wa_wh
    from routes.whatsapp_send_routes import register as reg_wa_send
    from routes.whatsapp_control_routes import register as reg_wa_ctrl
    from routes.wa_style_admin import register as reg_wa_admin

    from routes.telegram_webhook_routes import register as reg_tg_wh
    from routes.telegram_send_routes import register as reg_tg_send

    from routes.proactive_dispatch_routes import register as reg_proactive
    from routes.proactive_will_hook_routes import register as reg_will
    from routes.mail_compose_routes import register as reg_mail
    from routes.presets_routes import register as reg_presets
    from routes.messaging_health_routes import register as reg_health

    from metrics.messaging_metrics import register as reg_metrics

    app = current_app
    added = []
    for reg, name in [
        (reg_wa_wh, "wa_webhook"),
        (reg_wa_send, "wa_send"),
        (reg_wa_ctrl, "wa_ctrl"),
        (reg_wa_admin, "wa_admin"),
        (reg_tg_wh, "tg_webhook"),
        (reg_tg_send, "tg_send"),
        (reg_proactive, "proactive_dispatch"),
        (reg_will, "proactive_will_hook"),
        (reg_mail, "mail_compose"),
        (reg_presets, "presets"),
        (reg_health, "health"),
        (reg_metrics, "metrics"),
    ]:
        _safe_reg(app, reg, name, added)

    return jsonify({"ok": True, "registered": added})

def register(app):
    app.register_blueprint(bp)
    return bp