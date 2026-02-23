# -*- coding: utf-8 -*-
"""
routes/passport_routes.py - REST: /mem/passport/append

Mosty:
- Yavnyy: (Veb ↔ Profile) edinaya tochka dlya shtampov ot moduley i vneshnikh agentov.
- Skrytyy #1: (RBAC ↔ Ostorozhnost) pri zhelanii mozhno ogranichit zapis rolyami.
- Skrytyy #2: (SelfCatalog ↔ Prozrachnost) UI mozhet pokazyvat schetchiki.

Zemnoy abzats:
Knopka «proshtampovat»: vse vazhnye shagi popadayut v obschiy zhurnal, chtoby potom bylo chto proveryat.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("passport_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.passport import append as _append  # type: ignore
except Exception:
    _append=None  # type: ignore

@bp.route("/mem/passport/append", methods=["POST"])
def api_append():
    if _append is None: return jsonify({"ok": False, "error":"passport_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_append(str(d.get("note","")), dict(d.get("meta") or {}), str(d.get("source","app://unknown")), str(d.get("version","1"))))
# c=a+b