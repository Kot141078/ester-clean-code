# -*- coding: utf-8 -*-
"""routes/mm_enforcer_routes.py - REST dlya MM-enforcer.

Mosty:
- Yavnyy: (Veb ↔ Kod) ruchka skanirovaniya i chtenie otcheta.
- Skrytyy #1: (Prozrachnost ↔ Distsiplina) deshevyy linter na urovne servera.
- Skrytyy #2: (Operatsii ↔ Nochnaya uborka) udobno dergat iz /cron/run.

Zemnoy abzats:
Knopka “check the fabriku pamyati” - i otchet gotov.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_mm = Blueprint("mm_enforcer", __name__)

try:
    from modules.qa.mm_enforcer import scan as _scan, report as _report  # type: ignore
except Exception:
    _scan = _report = None  # type: ignore

def register(app):
    app.register_blueprint(bp_mm)

@bp_mm.route("/mm/enforce/scan", methods=["POST"])
def api_scan():
    if _scan is None: return jsonify({"ok": False, "error":"mm enforcer unavailable"}), 500
    return jsonify(_scan())

@bp_mm.route("/mm/enforce/report", methods=["GET"])
def api_report():
    if _report is None: return jsonify({"ok": False, "error":"mm enforcer unavailable"}), 500
    return jsonify(_report())
# c=a+b