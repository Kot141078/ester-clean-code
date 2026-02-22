# -*- coding: utf-8 -*-
"""
modules/security/consent_policy.py — policy-nastroyschik poverkh protokola soglasiy.

Ideya:
- Gibkie pravila «kogda sprashivat/razreshat/zapreschat» po (scope, title_pattern).
- Prioritet: allow > deny > ask > default(protocol mode).
- Sovmestimo s consent_protocol.request(): snachala policy, zatem (esli nuzhno) obschiy protokol.

Format: data/security/consent_policy.json
{
  "rules": [
    {"scope":"hotkey","title":"BankApp","decision":"deny"},
    {"scope":"mix_apply","title":"Notepad","decision":"allow","ttl":60},
    {"scope":"workflow","title":"*","decision":"ask"}
  ]
}

API:
- upsert(rule), remove(idx), list_rules(), decide(scope, title) -> {"decision":"allow|deny|ask","ttl"?:int}

MOSTY:
- Yavnyy: (Pravila ↔ Soglasiya) avtomatizatsiya rutiny, no uvazhenie voli.
- Skrytyy #1: (Logika ↔ Bezopasnost) chetkiy poryadok prioritetov.
- Skrytyy #2: (Memory ↔ UX) TTL umenshaet trenie pri seriyakh deystviy.

ZEMNOY ABZATs:
Prostoy JSON. Podstrochnye sopostavleniya; «*» — lyuboy zagolovok. Bez vneshnikh zavisimostey.

# c=a+b
"""
from __future__ import annotations
import os, json, fnmatch
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "security")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "consent_policy.json")

_DEF = {"rules": []}

def _load() -> Dict[str, Any]:
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_DEF, f, ensure_ascii=False, indent=2)
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(o: Dict[str, Any]) -> None:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)

def list_rules() -> List[Dict[str, Any]]:
    return _load().get("rules", [])

def upsert(rule: Dict[str, Any]) -> Dict[str, Any]:
    """rule = {scope,title,decision,ttl?} decision in allow|deny|ask"""
    obj = _load()
    arr = obj.get("rules", [])
    # zamenyaem po pare (scope,title)
    scope = (rule.get("scope") or "").strip().lower()
    title = (rule.get("title") or "*").strip()
    decision = (rule.get("decision") or "ask").strip().lower()
    ttl = int(rule.get("ttl", 0) or 0)
    arr = [r for r in arr if not (r.get("scope","")==scope and r.get("title","")==title)]
    arr.append({"scope": scope, "title": title, "decision": decision, "ttl": ttl})
    obj["rules"] = arr
    _save(obj)
    return {"ok": True, "count": len(arr)}

def remove(idx: int) -> Dict[str, Any]:
    obj = _load(); arr = obj.get("rules", [])
    if 0 <= idx < len(arr):
        del arr[idx]; obj["rules"] = arr; _save(obj)
        return {"ok": True, "count": len(arr)}
    return {"ok": False, "error": "bad_index"}

def decide(scope: str, title: str) -> Dict[str, Any]:
    scope = (scope or "").lower(); t = (title or "")
    rules = list_rules()
    # prioritet allow > deny > ask
    best: Optional[Dict[str, Any]] = None
    for d in ("allow","deny","ask"):
        for r in rules:
            if r.get("scope") == scope and (r.get("title") == "*" or _match(t, r.get("title",""))):
                if r.get("decision") == d:
                    best = r; break
        if best: break
    if not best:
        return {"ok": True, "decision": "pass"}
    out = {"ok": True, "decision": best.get("decision")}
    if best.get("ttl",0) > 0:
        out["ttl"] = int(best["ttl"])
    return out

def _match(s: str, pat: str) -> bool:
    # podstroka ili maska so zvezdochkoy
    if "*" in pat or "?" in pat:
        return fnmatch.fnmatch(s, pat)
    return pat.lower() in s.lower()