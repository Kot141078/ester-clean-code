# -*- coding: utf-8 -*-
"""
routes/healthz_routes.py - prostoy health-zond uzla.

Mosty:
- Yavnyy: (Monitoring ↔ Uzel) daet bazovuyu proverku zhizni HTTP-steka.
- Skrytyy #1: (A/B ↔ Avtootkat) ispolzuetsya v runtime/AB dlya sanity-check.
- Skrytyy #2: (Planirovschik ↔ Nablyudenie) mozhet dergatsya kronom.

Zemnoy abzats:
Kak «puls» u patsienta - bystryy otvet OK govorit, chto servis dyshit i gotov prinimat komandy.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("healthz_routes", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.route("/healthz", methods=["GET"])
def api_healthz():
    # Mozhno rasshiryat (proverki zavisimostey, diska, pamyati)
    return jsonify({"ok": True, "uptime_probe": "healthy"})
# c=a+b