# -*- coding: utf-8 -*-
"""modules/security/consent_protocol.py - lokalnyy protokol razresheniy.

Ponyatiya:
- Scope: "hotkey", "workflow", "mix_apply", "net_forward"
- Target: zagolovok okna or shablon deystviya
- TTL: srok deystviya razresheniya (sekundy)
- Modes: "ask_always" | "remember_ttl" | "deny_all"

Faily:
- data/security/consent.json (nastroyki)
- data/security/consent_cache.json (vremennye razresheniya s istecheniem)

API:
- set_mode(mode)
- request(scope, target, meta) -> {decision:"allow|deny|ask", ticket_id?}
- decide(ticket_id, allow:bool, ttl_sec:int)

MOSTY:
- Yavnyy: (Volya ↔ Deystvie) kazhdoe chuvstvitelnoe deystvie prokhodit yavnoe soglasie.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) protokoliruem “kto/chto/kuda”.
- Skrytyy #2: (Memory ↔ UX) TTL umenshaet trenie pri seriyakh odnorodnykh deystviy.

ZEMNOY ABZATs:
Simple JSON i kratkozhivuschie zapisi. UI pokazyvaet kartochku s voprosom.

# c=a+b"""
from __future__ import annotations
import os, json, time, uuid
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "security")
os.makedirs(DIR, exist_ok=True)
CONF = os.path.join(DIR, "consent.json")
CACHE = os.path.join(DIR, "consent_cache.json")

_DEF = {"mode":"ask_always"}

def _load(p: str, d: dict) -> dict:
    if not os.path.exists(p):
        with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

def _save(p: str, o: dict) -> None:
    with open(p,"w",encoding="utf-8") as f: json.dump(o,f,ensure_ascii=False,indent=2)

def set_mode(mode: str) -> Dict[str, Any]:
    mode = (mode or "ask_always").lower()
    if mode not in ("ask_always","remember_ttl","deny_all"):
        return {"ok": False, "error":"bad_mode"}
    cfg = _load(CONF,_DEF); cfg["mode"]=mode; _save(CONF,cfg)
    return {"ok": True, "mode":mode}

def _now() -> int: return int(time.time())

def _cache() -> dict: return _load(CACHE, {"tickets":{}, "permits":[]})

def request(scope: str, target: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load(CONF,_DEF); c = _cache()
    if cfg.get("mode") == "deny_all":
        return {"ok": True, "decision": "deny"}
    # find active resolution
    now = _now()
    for p in list(c.get("permits", [])):
        if now > int(p.get("exp",0)): continue
        if p.get("scope")==scope and p.get("target")==target:
            return {"ok": True, "decision": "allow", "permit": p}
    # if you’re a remember, we’ll suggest asking and remembering
    tid = str(uuid.uuid4())
    c["tickets"][tid] = {"scope":scope,"target":target,"meta":meta or {}, "ts": now}
    _save(CACHE, c)
    return {"ok": True, "decision": "ask", "ticket_id": tid, "mode": cfg.get("mode","ask_always")}

def decide(ticket_id: str, allow: bool, ttl_sec: int = 0) -> Dict[str, Any]:
    c = _cache()
    tk = (c.get("tickets") or {}).pop(ticket_id, None)
    _save(CACHE, c)
    if not tk:
        return {"ok": False, "error": "ticket_not_found"}
    if not allow:
        return {"ok": True, "decision": "deny"}
    if ttl_sec > 0:
        p = {"scope": tk["scope"], "target": tk["target"], "exp": _now()+int(ttl_sec)}
        c = _cache()
        c["permits"].append(p); _save(CACHE, c)
    return {"ok": True, "decision": "allow"}