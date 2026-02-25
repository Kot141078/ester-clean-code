# -*- coding: utf-8 -*-
"""modules/ops/consent.py - “pilyuli” soglasiya: vydacha, verifikatsiya, otzyv (one-time tokens TTL).

Mosty:
- Yavnyy: (Soglasie ↔ Risk) opasnye deystviya trebuyut yavnoy otmetki soglasiya.
- Skrytyy #1: (Infoteoriya ↔ Audit) tokeny khranim s naznacheniem, vremenem, TTL i statusom.
- Skrytyy #2: (Kibernetika ↔ UX) gibkost: privyazka k patternu/metodu, vozmozhnost otzyva.

Zemnoy abzats:
Odnorazovyy zheton: “Are you sure?” - vydal, ispolzoval, pogasil.

# c=a+b"""
from __future__ import annotations
import json, os, re, time, secrets
from typing import Any, Dict, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DIR = os.getenv("CONSENT_DIR","data/consent")
TTL = int(os.getenv("CONSENT_TTL_SEC","300") or "300")
STATE = os.path.join(DIR, "tokens.json")

def _ensure():
    os.makedirs(DIR, exist_ok=True)
    if not os.path.isfile(STATE):
        json.dump({"tokens": {}}, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _db() -> Dict[str,Any]:
    _ensure()
    return json.load(open(STATE,"r",encoding="utf-8"))

def _save(db: Dict[str,Any]):
    json.dump(db, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def issue(pattern: str, method: str, ttl: int | None = None, note: str = "") -> Dict[str,Any]:
    db=_db()
    tok = secrets.token_hex(16)
    db["tokens"][tok] = {
        "pattern": pattern,
        "method": method.upper(),
        "ts": int(time.time()),
        "ttl": int(ttl or TTL),
        "used": False,
        "note": note
    }
    _save(db)
    return {"ok": True, "token": tok, "expires_in": db["tokens"][tok]["ttl"]}

def verify(token: str, path: str, method: str) -> Tuple[bool, Dict[str,Any]]:
    if not token: 
        return False, {"error":"no_token"}
    db=_db()
    it = db["tokens"].get(token)
    if not it: 
        return False, {"error":"unknown_token"}
    if it.get("used"): 
        return False, {"error":"used"}
    if int(time.time()) - int(it.get("ts",0)) > int(it.get("ttl",0)):
        return False, {"error":"expired"}
    try:
        if not re.match(str(it.get("pattern","^$")), path or ""):
            return False, {"error":"pattern_mismatch"}
    except re.error:
        return False, {"error":"bad_pattern"}
    if method.upper() != str(it.get("method","GET")).upper():
        return False, {"error":"method_mismatch"}
    # pomechaem ispolzovannym
    it["used"] = True
    db["tokens"][token] = it
    _save(db)
    return True, {"ok": True}

def revoke(token: str) -> Dict[str,Any]:
    db=_db()
    if token in db["tokens"]:
        del db["tokens"][token]
        _save(db)
        return {"ok": True}
    return {"ok": False, "error":"not_found"}

def list_tokens() -> Dict[str,Any]:
    db=_db()
    # hide actual tokens - meta only (except debug mode)
    items=[]
    for t, meta in (db.get("tokens") or {}).items():
        items.append({"hint": t[:6]+"…", **{k:meta[k] for k in meta if k!="pattern"}, "pattern": meta.get("pattern")})
    return {"ok": True, "count": len(items), "items": items}
# c=a+b