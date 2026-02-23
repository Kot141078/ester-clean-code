# -*- coding: utf-8 -*-
"""
routes/hw_routes.py - REST dlya apparatnogo statusa.

Mosty:
- Yavnyy: (Veb ↔ Zhelezo) bystryy srez.
- Skrytyy #1: (Operatsii ↔ Nablyudaemost) prigodno dlya paneley.
- Skrytyy #2: (Vyzhivanie ↔ Degradatsiya) mozhno triggerit mery pri nekhvatke.

Zemnoy abzats:
Proverili «zdorove zheleza» - reshili, kak zhit dalshe.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hw = Blueprint("hw", __name__)

try:
    from modules.hw.monitor import status as _status  # type: ignore
except Exception:
    _status = None  # type: ignore

def register(app):
    app.register_blueprint(bp_hw)

@bp_hw.route("/hardware/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"hw monitor unavailable"}), 500
    return jsonify(_status())
# c=a+b