# -*- coding: utf-8 -*-
"""
routes/resilience_boot_routes.py - REST: boot-status i repair.

Mosty:
- Yavnyy: (Veb ↔ DevOps) bystryy audit i pochinka struktury data/*.
- Skrytyy #1: (Integratsiya ↔ AppOps+) udobno dergat pri zapuske/migratsii.
- Skrytyy #2: (Ustoychivost ↔ Samosborka) baza dlya auto-bootstrap stsenariev.

Zemnoy abzats:
Esli chego-to ne khvataet - sozdaem po umolchaniyu i zapuskaem dalshe.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_boot = Blueprint("resilience_boot", __name__)

try:
    from modules.resilience.boot import status as _st, repair as _rep  # type: ignore
except Exception:
    _st=_rep=None  # type: ignore

def register(app):
    app.register_blueprint(bp_boot)

@bp_boot.route("/resilience/boot/status", methods=["GET"])
def api_st():
    if _st is None: return jsonify({"ok": False, "error":"boot_unavailable"}), 500
    return jsonify(_st())

@bp_boot.route("/resilience/boot/repair", methods=["POST"])
def api_rep():
    if _rep is None: return jsonify({"ok": False, "error":"boot_unavailable"}), 500
    return jsonify(_rep())
# c=a+b