# -*- coding: utf-8 -*-
"""
routes/policy_pill_routes.py - REST: /policy/pill/* - konfiguratsiya patternov «pilyuli».

Mosty:
- Yavnyy: (Politika ↔ Guard) tsentralizovannoe upravlenie spiskom trebuyuschikh podtverzhdeniya ruchek.
- Skrytyy #1: (Profile ↔ Audit) zapis fakta izmeneniya politiki.
- Skrytyy #2: (RBAC ↔ Bezopasnost) izmenenie karty - administrativnaya operatsiya.

Zemnoy abzats:
Spisok «krasnykh knopok» pod steklom. Menyaem ego v odnom meste, guard podkhvatit avtomaticheski.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("policy_pill_routes", __name__)

def register(app):
    app.register_blueprint(bp)

PATF=os.getenv("PILL_PATTERNS","data/policy/pill_patterns.json")
os.makedirs(os.path.dirname(PATF), exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "policy://pill")
    except Exception:
        pass

@bp.route("/policy/pill/status", methods=["GET"])
def api_status():
    pats=[]
    try:
        if os.path.isfile(PATF):
            j=json.load(open(PATF,"r",encoding="utf-8"))
            pats=list(j.get("patterns") or [])
    except Exception:
        pass
    return jsonify({"ok": True, "patterns": pats})

@bp.route("/policy/pill/config", methods=["POST"])
def api_config():
    d=request.get_json(True, True) or {}
    pats=list(d.get("patterns") or [])
    if not isinstance(pats, list): return jsonify({"ok": False, "error":"bad_patterns"}), 400
    json.dump({"patterns": pats, "t": int(time.time())}, open(PATF,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    _passport("pill_patterns_update", {"count": len(pats)})
    return jsonify({"ok": True, "count": len(pats)})
# c=a+b