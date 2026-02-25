# -*- coding: utf-8 -*-
"""routes/self_creed_integrity_routes.py - REST dlya otpechatka/yakorya/proverki i tsepochki sobytiy poslaniya.

Endpoint:
  • GET /self/cread/fingerprint
  • POST /self/cread/anchor/init
  • POST /self/cred/verify
  • GET /self/cread/chain
  • GET /metrics/self_creed_integrity

Mosty:
- Yavnyy: (Infoteoriya ↔ Audit) lyuboy mozhet proverit “to samoe” poslanie cherez khesh i (opts.) podpis.
- Skrytyy #1: (Kibernetika ↔ Kontrol) strogiy rezhim mozhet blokirovat riskovannye deystviya pri nesootvetstvii.
- Skrytyy #2: (Set ↔ Sestry) khvost tsepochki mozhno replitsirovat mezhdu uzlami.

Zemnoy abzats:
Eto plomba i zhurnal u seyfa: vidno khesh “kak bylo”, vidno lyubye troganiya i mozhno sverit po mestu.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_creed_int = Blueprint("self_creed_integrity", __name__)

try:
    from modules.self.creed_integrity import fingerprint, anchor_init, verify, chain_tail, _CNT  # type: ignore
except Exception:
    fingerprint = anchor_init = verify = chain_tail = None  # type: ignore
    _CNT = {"anchor_inits":0,"verify_calls":0,"verify_ok":0,"verify_fail":0,"chain_appends":0}

def register(app):
    app.register_blueprint(bp_creed_int)

@bp_creed_int.route("/self/creed/fingerprint", methods=["GET"])
def api_fp():
    if fingerprint is None:
        return jsonify({"ok": False, "error": "creed_integrity unavailable"}), 500
    return jsonify(fingerprint())

@bp_creed_int.route("/self/creed/anchor/init", methods=["POST"])
def api_anchor():
    if anchor_init is None:
        return jsonify({"ok": False, "error": "creed_integrity unavailable"}), 500
    force = bool((request.get_json(True, True) or {}).get("force", False))
    return jsonify(anchor_init(force=force))

@bp_creed_int.route("/self/creed/verify", methods=["POST"])
def api_verify():
    if verify is None:
        return jsonify({"ok": False, "error": "creed_integrity unavailable"}), 500
    return jsonify(verify())

@bp_creed_int.route("/self/creed/chain", methods=["GET"])
def api_chain():
    if chain_tail is None:
        return jsonify({"ok": False, "error": "creed_integrity unavailable"}), 500
    return jsonify(chain_tail())

@bp_creed_int.route("/metrics/self_creed_integrity", methods=["GET"])
def metrics():
    return (f"creed_anchor_inits_total {_CNT.get('anchor_inits',0)}\n"
            f"creed_verify_calls_total {_CNT.get('verify_calls',0)}\n"
            f"creed_verify_ok_total {_CNT.get('verify_ok',0)}\n"
            f"creed_verify_fail_total {_CNT.get('verify_fail',0)}\n"
            f"creed_chain_appends_total {_CNT.get('chain_appends',0)}\n",
            200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
# c=a+b