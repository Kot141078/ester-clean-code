# -*- coding: utf-8 -*-
"""modules/caution/pill.py - odnorazovye “pilyuli” predostorozhnosti (odnorazovye tokeny).

Mosty:
- Yavnyy: (Ostorozhnost ↔ Ruchki) vydaem i proveryaem tokeny dlya chuvstvitelnykh marshrutov.
- Skrytyy #1: (RBAC ↔ Trust) mozhet rabotat vmeste s rolyami/zagolovkom X-Subject, ne lomaya ikh.
- Skrytyy #2: (Audit ↔ Memory) sobytiya vydachi/verki mozhno pisat v pamyat cherez passport (po mestu vyzova).

Zemnoy abzats:
Kak odnorazovyy klyuch ot seyfa - deystvuet korotkoe vremya i propadaet posle ispolzovaniya.

# c=a+b"""
from __future__ import annotations
import os, json, time, secrets, re
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("PILL_DB","data/security/pills.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"tokens":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def issue(pattern: str, method: str = "POST", ttl: int = 300, subject: str | None = None) -> Dict[str,Any]:
    """pattern: route regex; metnode: expected HTTP method; ttl: sec."""
    _ensure()
    tok = secrets.token_urlsafe(24)
    j=_load()
    j["tokens"][tok]={"pattern": pattern, "method": method.upper(), "exp": int(time.time())+max(5,ttl), "sub": subject or ""}
    _save(j)
    return {"ok": True, "token": tok, "expires_in": ttl}

def verify(token: str, pattern: str | None = None, method: str | None = None, subject: str | None = None, consume: bool = True) -> Dict[str,Any]:
    """Token verification. If consume=Three - one-time (a successful check deletes the token)."""
    if not token: return {"ok": False, "error":"no_token"}
    j=_load(); t=j["tokens"].get(token)
    if not t: return {"ok": False, "error":"not_found_or_used"}
    if int(time.time()) >= int(t.get("exp",0)): 
        del j["tokens"][token]; _save(j); 
        return {"ok": False, "error":"expired"}
    # method must match if given
    if method and t.get("method","") != method.upper():
        return {"ok": False, "error":"method_mismatch"}
    # the pattern must match the expected/actual
    pat = pattern or t.get("pattern","")
    try:
        if not re.match(pat, t.get("pattern","")) and not re.match(t.get("pattern",""), pat):
            return {"ok": False, "error":"pattern_mismatch"}
    except Exception:
        pass
    # subject (if set at issuance), may be empty
    sub_need=(t.get("sub","") or "")
    if sub_need and (subject or "") != sub_need:
        return {"ok": False, "error":"subject_mismatch"}
    if consume:
        try: del j["tokens"][token]
        except Exception: pass
        _save(j)
    return {"ok": True}
# c=a+b