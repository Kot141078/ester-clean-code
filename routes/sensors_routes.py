# -*- coding: utf-8 -*-
"""
routes/sensors_routes.py - REST/UI dlya datchikov konteksta.

Mosty:
- Yavnyy: (UI/HTTP ↔ Sensors) - bystryy snapshot okruzheniya offlayn.
- Skrytyy 1: (Planirovanie ↔ Memory) - snapshot prigoden dlya apstrim-logiki (adaptatsiya povedeniya).
- Skrytyy 2: (Nablyudaemost ↔ Diagnostika) - mozhno dergat iz health-stranits.

Zemnoy abzats:
Otkryl stranitsu - vidish, «zhiva li mashina», skolko mesta na diske i kakov obschiy tonus sistemy.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from modules.physio.sensors import snapshot
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("sensors_routes", __name__, url_prefix="/sensors")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.get("/snapshot")
def snap():
    return jsonify(snapshot())

@bp.get("/admin")
def admin():
    # minimalnaya adminka bez otdelnogo shablona
    return render_template("admin_sensors.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b