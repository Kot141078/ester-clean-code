# -*- coding: utf-8 -*-
"""
routes/mem_mm_lint_routes.py - REST: otchet lintera «ispolzuyte get_mm()».

Mosty:
- Yavnyy: (Veb ↔ Kachestvo) pokazat naydennye obkhody fabriki pamyati.
- Skrytyy #1: (DevOps ↔ Cron) mozhno zapuskat po raspisaniyu.
- Skrytyy #2: (UX ↔ Panel) bystryy spisok dlya ispravleniy.

Zemnoy abzats:
Odin vyzov - i vidno, gde narushayut kontrakt pamyati.
# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mmlint = Blueprint("mem_mm_lint", __name__)

try:
    from modules.mm.lint import scan as _scan  # type: ignore
except Exception:
    _scan = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mmlint)

@bp_mmlint.route("/mem/mm/lint", methods=["GET"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"mmlint_unavailable"}), 500
    return jsonify(_scan())
# c=a+b