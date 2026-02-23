# -*- coding: utf-8 -*-
"""
routes/sandbox_routes.py - REST: zapusk Python v pesochnitse.

Mosty:
- Yavnyy: (Veb ↔ Pesochnitsa) edinaya tochka dlya prob.
- Skrytyy #1: (CautionNet ↔ Consent) trebuet «pilyulyu».
- Skrytyy #2: (UX ↔ Panel) udobno vstroit knopku «proverit».

Zemnoy abzats:
«Snachala na stolike, potom v operatsionnoy».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sbx = Blueprint("sandbox_routes", __name__)

try:
    from modules.sandbox.py_runner import run_py as _run  # type: ignore
except Exception:
    _run=None  # type: ignore

def register(app):
    app.register_blueprint(bp_sbx)

@bp_sbx.route("/sandbox/py/run", methods=["POST"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"sandbox_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_run(str(d.get("code",""))))
# c=a+b