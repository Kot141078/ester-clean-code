# -*- coding: utf-8 -*-
"""
middleware/rbac.py — prostaya rolevaya model poverkh JWT/lokalnoy karty.

Mosty:
- Yavnyy: (Bezopasnost ↔ Routy) chek roli po subject.
- Skrytyy #1: (DevOps ↔ Bootstrap) pervyy admin cherez sekret.
- Skrytyy #2: (Ostorozhnost ↔ Caution) druzhit s «pilyulyami» cherez otdelnyy sloy.

Zemnoy abzats:
Komu mozhno nazhimat opasnye knopki — derzhim spisok i proveryaem.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("RBAC_DB","data/security/roles.json")
BOOT=os.getenv("RBAC_BOOTSTRAP_SECRET","").strip()

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"roles":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def get_roles()->Dict[str,Any]:
    _ensure(); return json.load(open(DB,"r",encoding="utf-8"))

def set_roles(obj: Dict[str,Any])->Dict[str,Any]:
    _ensure(); json.dump(obj, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True}

ORDER={"viewer":1,"operator":2,"admin":3}

def _subject_from_request(flask_request) -> str:
    # pytaemsya dostat subject iz JWT/zagolovkov; bezopasnyy defolt — anonymous
    sub = flask_request.headers.get("X-Subject","anonymous")
    return sub

def allowed(flask_request, min_role: str) -> bool:
    cur=get_roles()
    sub=_subject_from_request(flask_request)
    role=(cur.get("roles",{}).get(sub) or "viewer")
    return ORDER.get(role,0) >= ORDER.get(min_role,2)

def bootstrap_ok(secret: str)->bool:
    return bool(BOOT) and (secret==BOOT)
# c=a+b