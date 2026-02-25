# -*- coding: utf-8 -*-
"""modules/security/pill_guard.py - before_request guard: proverka “pilyuli” (chelovek v konture).

Mosty:
- Yavnyy: (Politika ↔ Riski) perekhvatyvaem izmenyayuschie zaprosy, trebuem podtverzhdenie po pravilam.
- Skrytyy #1: (Caution Rules ↔ Tsentralizatsiya) chitaem i svoi PATTERNS, i lyubye data/policy/caution_rules.* (requires_pill:true).
- Skrytyy #2: (Profile ↔ Audit) sozdaem zayavku srazu pri pervom obraschenii, vozvraschaem 428 s id.

Zemnoy abzats:
Eto kak “kod iz SMS”: bez deystvuyuschey zayavki s vernym otpechatkom tela zaprosa deystvie ne proydet.

# c=a+b"""
from __future__ import annotations
import os, re, json, time, hashlib
from typing import List, Dict, Any
from flask import current_app, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PATF=os.getenv("PILL_PATTERNS","data/policy/pill_patterns.json")
HEADER=os.getenv("PILL_HEADER","X-Pill")

_cache={"ts":0,"patterns":[]}

def _sha256(b: bytes)->str:
    import hashlib; return hashlib.sha256(b or b"").hexdigest()

def _load_patterns()->List[Dict[str,str]]:
    pats=[]
    # 1) Explicit config
    if os.path.isfile(PATF):
        try:
            j=json.load(open(PATF,"r",encoding="utf-8"))
            for x in j.get("patterns",[]):
                m=str(x.get("method","")).upper().strip()
                r=str(x.get("pattern","")).strip()
                if m and r: pats.append({"method": m, "pattern": r})
        except Exception:
            pass
    # 2) Vse caution_rules.* so flagom requires_pill:true
    try:
        for name in os.listdir("data/policy"):
            if not name.startswith("caution_rules"): continue
            try:
                j=json.load(open(os.path.join("data/policy",name),"r",encoding="utf-8"))
                for r in j.get("rules",[]):
                    if r.get("requires_pill", False):
                        pats.append({"method": str(r.get("method","GET")).upper(), "pattern": str(r.get("pattern","")).strip()})
            except Exception:
                continue
    except Exception:
        pass
    return pats

def _need_pill(method: str, path: str)->bool:
    now=int(time.time())
    if now - int(_cache["ts"]) > 5:
        _cache["patterns"]=_load_patterns(); _cache["ts"]=now
    for r in _cache["patterns"]:
        if r["method"]==method and re.match(r["pattern"], path):
            return True
    return False

def register(app):
    @app.before_request
    def _pill_check():
        method=request.method.upper()
        if method not in ("POST","PUT","PATCH","DELETE"): return
        path=request.path
        if not _need_pill(method, path): return
        body=request.get_data() or b""
        sig=_sha256(body)
        # If you receive a valid S-Pill, we’ll check it.
        token=request.headers.get(HEADER,"").strip()
        if token:
            try:
                from modules.policy.pillbox import get as _get  # type: ignore
                rep=_get(token)
                if rep.get("ok"):
                    pill=rep["pill"]
                    if pill.get("status")=="approved" and pill.get("method")==method and pill.get("path")==path and pill.get("sha256")==sig:
                        return  # propuskaem
            except Exception:
                pass
        # Otherwise, creates a request and blocks 428
        try:
            from modules.policy.pillbox import request as _req  # type: ignore
            p=_req(method, path, sig, None, note="auto", src_ip=request.remote_addr or "")
            return jsonify({"ok": False, "error":"pill_required", "pill": p.get("pill"), "info": {"header": HEADER}}), 428
        except Exception:
            return jsonify({"ok": False, "error":"pill_required", "pill": None, "info": {"header": HEADER}}), 428
# c=a+b