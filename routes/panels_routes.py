# -*- coding: utf-8 -*-
"""
routes/panels_routes.py - edinaya HTML-panel Ops dlya upravleniya novymi vozmozhnostyami.

Mosty:
- Yavnyy: (UX ↔ Operatsii) odna tochka vkhoda dlya health/guarded-apply/rollback/media/quorum/release/backup.
- Skrytyy #1: (Kibernetika ↔ Kontrol) operator i «volya» vidyat odni i te zhe rychagi.
- Skrytyy #2: (Bezopasnost ↔ Trust) chuvstvitelnye deystviya ostayutsya za «pilyuley»/RBAC.

Zemnoy abzats:
Otkryl stranitsu - vidish zdorove, mozhesh akkuratno primenit pravku ili otkatit, dernut mediatik i t. p.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, send_from_directory, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_panels = Blueprint("panels_routes", __name__, static_folder="static", static_url_path="/panel_static")

def register(app):
    app.register_blueprint(bp_panels)

@bp_panels.route("/panel/ops", methods=["GET"])
def panel_ops():
    # Otdaem staticheskuyu HTML-stranitsu paneli
    return send_from_directory("static/panels", "ops.html")

@bp_panels.route("/panel/ping", methods=["GET"])
def panel_ping():
    return jsonify({"ok": True})
# c=a+b