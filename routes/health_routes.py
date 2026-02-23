# -*- coding: utf-8 -*-
"""
routes.health_routes - minimalnyy health JSON.

MOSTY:
- Yavnyy: Inzhenernaya diagnostika ↔ Polzovatelskiy kontrol - vydaem kompaktnyy status yadra.
- Skrytyy 1: Bayes - schitaem «zdorove» po nablyudaemym priznakam (kol-vo zaregistrirovannykh/propuschennykh).
- Skrytyy 2: Kibernetika - health kak sensor v konture upravleniya (vneshniy kontroller mozhet reshat ob otkate/perezapuske).

ZEMNOY ABZATs:
Kak pulsoksimetr: prostoy pribor, no govorit glavnoe - zhiv/stabilen, gde shum/nedobor.
"""
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("health", __name__)

@bp.get("/health")
def health():
    info = current_app.config.get("ESTER_BOOT_INFO", {})
    reg = info.get("registered", []) if isinstance(info, dict) else []
    skipped = info.get("skipped", {}) if isinstance(info, dict) else {}
    return jsonify({
        "ok": True,
        "registered_count": len(reg),
        "skipped": skipped,
    })
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app