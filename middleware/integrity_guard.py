# -*- coding: utf-8 -*-
"""middleware/integrity_guard.py - okhrannik tselostnosti: trebuet korrektnuyu podpis .sig.json pri registratsii moduley (v A-rezhime).

Mosty:
- Yavnyy: (Bezopasnost ↔ Rasshiryaemost) ne podklyuchaem modul, esli net podpisi.
- Skrytyy #1: (Infoteoriya ↔ Audit) obyasnyaem pochemu otkaz.
- Skrytyy #2: (Kibernetika ↔ A/B) myagkiy rezhim B (log) — ne blokiruet.

Zemnoy abzats:
“Bez pechati - ne pustim v sistemu”: zaschita ot podsovyvaemykh faylov.

# c=a+b"""
from __future__ import annotations
import os, json, re
from typing import Any, Dict
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_integrity = Blueprint("integrity_guard", __name__)

AB = (os.getenv("TRUST_AB","A") or "A").upper()
ENFORCE = (os.getenv("INTEGRITY_ENFORCE","false").lower()=="true")

def _verify_sig_file(py_module_path: str) -> Dict[str,Any]:
    sig_path = py_module_path + ".sig.json"
    if not os.path.isfile(sig_path):
        return {"ok": False, "error":"no_sig_file", "sig_path": sig_path}
    try:
        sig=json.load(open(sig_path,"r",encoding="utf-8"))
        from modules.trust.sign import verify_sig  # type: ignore
        rep=verify_sig(sig)
        if not rep.get("ok"): 
            return {"ok": False, "error":"sig_mismatch", "detail": rep}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"sig_error:{e}"}

@bp_integrity.before_app_request
def guard():
    if not ENFORCE and AB!="A":
        return None
    # we check only /app/discover/register
    if request.path != "/app/discover/register" or request.method != "POST":
        return None
    d = request.get_json(silent=True) or {}
    mods = list(d.get("modules") or [])
    errs=[]
    for m in mods:
        try:
            import importlib.util
            spec = importlib.util.find_spec(m)
            if not spec or not spec.origin: 
                errs.append({"module": m, "error":"not_found"}); continue
            rep=_verify_sig_file(spec.origin)
            if not rep.get("ok"):
                errs.append({"module": m, **rep})
        except Exception as e:
            errs.append({"module": m, "error": str(e)})
    if errs and (ENFORCE or AB=="A"):
        resp= jsonify({"ok": False, "error":"integrity_failed", "violations": errs})
        resp.status_code = 412
        return resp
    return None

def register(app):
    app.register_blueprint(bp_integrity)
# c=a+b