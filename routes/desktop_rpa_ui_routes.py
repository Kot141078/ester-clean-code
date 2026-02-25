# -*- coding: utf-8 -*-
"""routes/desktop_rpa_ui_routes.py - prostaya stranitsa upravleniya virtualnym stolom Ester.

MOSTY:
- Yavnyy: (UX ↔ Deystviya) knopki UI vyzyvayut /desktop/rpa/*.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) vse deystviya cherez edinyy REST-proksi s proverkami.
- Skrytyy #2: (Kibernetika ↔ Volya) chelovek i pravila myshleniya mogut zapuskat odni i te zhe stsenarii.

ZEMNOY ABZATs:
Daet operatoru ponyatnyy “pult”: proverka, zapusk terminala/bloknota, klik, vvod teksta.
Oflayn, only localhost, s zhurnalom v rpa.jsonl.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_rpa_ui", __name__)

@bp.route("/admin/desktop/rpa", methods=["GET"])
def admin_desktop_rpa():
    return render_template("admin_desktop_rpa.html")

def register(app):
    app.register_blueprint(bp)