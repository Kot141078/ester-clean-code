# -*- coding: utf-8 -*-
"""routes/self_sign_routes.py - REST: podpis i proverka snapshotov.

Mosty:
- Yavnyy: (Veb ↔ Podpisi) prostye ruchki podpisat/proverit arkhiv.
- Skrytyy #1: (Infoteoriya ↔ Audit) .sig.json ryadom s arkhivom.
- Skrytyy #2: (Vyzhivanie ↔ Samodeploy) v svyazke s invite - bezopasnyy approve.

Zemnoy abzats:
Knopki “podpisat” i “proverit” arkhiv - dlya bystroy uverennosti pered razvertyvaniem.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sig = Blueprint("self_sign", __name__)

try:
    from modules.self.sigpack import sign_archive, verify_archive  # type: ignore
except Exception:
    sign_archive = verify_archive = None  # type: ignore

def register(app):
    app.register_blueprint(bp_sig)

@bp_sig.route("/self/pack/sign", methods=["POST"])
def api_sign():
    if sign_archive is None: return jsonify({"ok": False, "error":"sigpack unavailable"}), 500
    d = (request.get_json(True, True) or {})
    return jsonify(sign_archive(str(d.get("archive",""))))

@bp_sig.route("/self/pack/verify", methods=["POST"])
def api_verify():
    if verify_archive is None: return jsonify({"ok": False, "error":"sigpack unavailable"}), 500
    d = (request.get_json(True, True) or {})
    return jsonify(verify_archive(str(d.get("archive",""))))
# c=a+b