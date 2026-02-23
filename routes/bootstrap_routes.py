# -*- coding: utf-8 -*-
"""
routes/bootstrap_routes.py - REST: bootstrap-kombo (merge policy, refresh discover).

Mosty:
- Yavnyy: (Operatsii ↔ Udobstvo) odna knopka dlya privedeniya sredy v poryadok.
- Skrytyy #1: (Infoteoriya ↔ Audit) vozvraschaem podrobnyy otchet.
- Skrytyy #2: (Avtonomiya ↔ Planer) udobno vyzyvat iz cron/planirovschika.

Zemnoy abzats:
Nazhal «privesti v poryadok» - pravila sshilis, sistema osmotrelas.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_boot = Blueprint("app_bootstrap", __name__)

try:
    from modules.bootstrap.merge_policies import merge as _merge  # type: ignore
    from modules.app.discover import scan_modules as _scan  # type: ignore
except Exception:
    _merge = _scan = None  # type: ignore

def register(app):
    app.register_blueprint(bp_boot)

@bp_boot.route("/app/bootstrap/merge_policies", methods=["POST"])
def api_merge():
    if _merge is None: return jsonify({"ok": False, "error":"merge unavailable"}), 500
    return jsonify(_merge())

@bp_boot.route("/app/bootstrap/run", methods=["POST"])
def api_run():
    rep={}
    if _merge: rep["merge"]=_merge()
    if _scan: rep["discover"]= _scan()
    rep["ok"] = all((rep.get("merge",{}).get("ok",True), rep.get("discover",{}).get("ok",True)))
    return jsonify(rep)
# c=a+b