# -*- coding: utf-8 -*-
"""routes/mem_retro_linker_routes.py - REST-obertka dlya avto-linkovki pamyati.

Mosty:
- Yavnyy: (Veb ↔ Avtolinker) ruchka zapuska obrabotki poslednikh zapisey pamyati.
- Skrytyy #1: (RBAC ↔ JWT) optsionalno trebuet role operator/admin.
- Skrytyy #2: (Volya ↔ Plan) ekshen “mem.autolink.tick” vyzyvaet tot zhe kod.

Zemnoy abzats:
This is “knopka sekretarya”: nazhali - on probezhal po dnevniku i razlozhil nitochki po karte znaniy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_retro_linker_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mem.retro_linker import tick as _tick  # type: ignore
except Exception:
    _tick=None  # type: ignore

# simple RVACh check based on gastrointestinal tract (if enabled)
def _rbac_ok(role: str)->bool:
    if (os.getenv("RBAC_REQUIRED","true").lower()=="false"): return True
    try:
        from modules.auth.rbac import has_any_role  # type: ignore
        return has_any_role([role,"admin"])
    except Exception:
        return True  # v otsutstvii RBAC ne blokiruem

@bp.route("/mem/autolink/tick", methods=["POST"])
def api_autolink_tick():
    if _tick is None: return jsonify({"ok": False, "error":"autolink_unavailable"}), 500
    if not _rbac_ok("operator"): return jsonify({"ok": False, "error":"forbidden"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_tick(d.get("limit")))
# c=a+b