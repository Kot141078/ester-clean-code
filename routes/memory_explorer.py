# -*- coding: utf-8 -*-
"""routes/memory_explorer.py - web-obozrevatel pamyati.

MOSTY:
- (Yavnyy) GET /mem/explorer (HTML), API vnutri stranitsy bet /mem/search i /mem/get/<id>.
- (Skrytyy #1) Ne menyaet kontrakty /mem/*; eto chistyy interfeys poverkh nikh.
- (Skrytyy #2) Pokazyvaet layer/vid/metadannye; gotov k linkovke s suschnostyami.

ZEMNOY ABZATs:
Kak “kartotechnyy shkaf”: iskat, prolistyvat, otkryvat kartochku.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_explorer", __name__, url_prefix="/mem")

def register(app):
    app.register_blueprint(bp)

@bp.get("/explorer")
def explorer():
    return render_template("memory_explorer.html")
# c=a+b