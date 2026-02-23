# -*- coding: utf-8 -*-
"""
routes/messaging_console.py - Edinaya panel «Marshrutizatsiya i golos».

MOSTY:
- (Yavnyy) /messaging/admin - operatorskaya panel: predprosmotr pisma, golos avtora, presety, otpravka/marshrutizatsiya.
- (Skrytyy #1) Rabotaet poverkh uzhe vydannykh API: /mail/compose/preview, /voice/api/preview, /presetsx/*, /proactive/dispatch.
- (Skrytyy #2) Vstroennyy test avtoinferensa auditorii (chekboks).

ZEMNOY ABZATs:
Daet «odin ekran» dlya proverki, kak Ester zvuchit i kak ona marshrutiziruet soobscheniya po kanalam.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("messaging_console", __name__, template_folder="../templates")

@bp.route("/messaging/admin", methods=["GET"])
def admin():
    return render_template("messaging_console.html")

def register(app):
    app.register_blueprint(bp)
    return bp