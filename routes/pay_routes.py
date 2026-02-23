# -*- coding: utf-8 -*-
"""
routes/pay_routes.py - REST: /pay/prefs (get/set)

Mosty:
- Yavnyy: (Veb ↔ PayPrefs) tsentralizovannaya tochka dlya rekvizitov Papy.
- Skrytyy #1: (Outreach/Invoices ↔ Podstanovka) dokumenty tyanut otsyuda instruktsii.
- Skrytyy #2: (Passport ↔ Prozrachnost) obnovleniya fiksiruyutsya.

Zemnoy abzats:
Odin spravochnik - menshe oshibok v schetakh i pismakh.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("pay_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.pay.prefs import get as _get, set_ as _set  # type: ignore
except Exception:
    _get=_set=None  # type: ignore

@bp.route("/pay/prefs", methods=["GET"])
def api_get():
    if _get is None: return jsonify({"ok": False, "error":"pay_unavailable"}), 500
    return jsonify(_get())

@bp.route("/pay/prefs", methods=["POST"])
def api_set():
    if _set is None: return jsonify({"ok": False, "error":"pay_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_set(d))
# c=a+b