# -*- coding: utf-8 -*-
"""modules/thinking/rules_engine.py - dvizhok pravil “voli”: sobytiya/patterny → eksheny.

Mosty:
- Yavnyy: (Sobytiya ↔ Eksheny) edinyy sloy: “esli... to...” dlya vnutrennikh protsessov.
- Skrytyy #1: (Profile ↔ Audit) vypolnenie pravil shtampuetsya, udobno razbirat posledstviya.
- Skrytyy #2: (Cron/Watch ↔ Avtonomiya) pravila mozhno dergat po raspisaniyu i ot scanera papok.

Zemnoy abzats:
This is “rele”: nashla povod - zamknula tsep - vypolnila nuzhnye deystviya. Bez demonov, po knopke or po kronu.

# c=a+b"""
from __future__ import annotations
import os, json, time, fnmatch
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("THINK_RULES_DB","data/thinking/rules.json")
ENABLED=(os.getenv("THINK_RULES_ENABLE","true").lower()=="true")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"rules":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def list_rules()->Dict[str,Any]:
    return _load()

def set_rules(rules: List[Dict[str,Any]])->Dict[str,Any]:
    j={"rules": list(rules or [])}
    _save(j)
    _passport("rules_set", {"n": len(rules)})
    return {"ok": True, "n": len(rules)}

def _passport(note: str, meta: Dict[str,Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "thinking://rules")
    except Exception:
        pass

def _action_call(name: str, args: Dict[str,Any])->Dict[str,Any]:
    # call via HTTP to existing handles (universal)
    try:
        import urllib.request, json as _j
        route_map={
            "media.video.ingest": ("/media/video/ingest","POST"),
            "mem.passport.append": ("/mem/passport/append","POST"),
            "rag.hybrid.search": ("/rag/hybrid/search","POST"),
            "p2p.bloom.add": ("/p2p/bloom/add","POST")
        }
        path, method = route_map.get(name, ("", "POST"))
        if not path: return {"ok": False, "error":"unknown_action", "name": name}
        data=_j.dumps(args or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return _j.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e), "name": name}

def _subst(s: str, ctx: Dict[str,Any])->str:
    if not isinstance(s, str): return s
    out=s
    for k,v in (ctx or {}).items():
        out=out.replace("${"+str(k)+"}", str(v))
    return out

def _subst_obj(o: Any, ctx: Dict[str,Any])->Any:
    if isinstance(o, dict):
        return {k:_subst_obj(v, ctx) for k,v in o.items()}
    if isinstance(o, list):
        return [_subst_obj(x, ctx) for x in o]
    if isinstance(o, str):
        return _subst(o, ctx)
    return o

def _match(rule: Dict[str,Any], ctx: Dict[str,Any])->bool:
    m=rule.get("match") or {}
    # prostye polya: ext_any, name_glob
    ext_any=m.get("ext_any") or []
    if ext_any and ctx.get("ext"):
        if str(ctx.get("ext")).lower() not in [e.lower() for e in ext_any]:
            return False
    name_glob=m.get("name_glob")
    if name_glob and ctx.get("basename"):
        if not fnmatch.fnmatch(str(ctx.get("basename")), str(name_glob)):
            return False
    return True

def evaluate(context: Dict[str,Any])->Dict[str,Any]:
    if not ENABLED:
        return {"ok": False, "error":"rules_disabled"}
    rules = (_load().get("rules") or [])
    when = str(context.get("when") or context.get("kind") or "manual")
    hits=[]
    for r in rules:
        if str(r.get("when","")) not in ("on_watch_new","manual","cron"):
            continue
        if r.get("when") in ("manual","cron") and when not in ("manual","cron"):
            continue
        if not _match(r, context):
            continue
        # podstavim peremennye iz konteksta i ispolnim do[]
        local=[]
        for step in (r.get("do") or []):
            args=_subst_obj(step.get("args") or {}, context)
            rep=_action_call(step.get("action",""), args)
            local.append({"action": step.get("action",""), "args": args, "result_ok": bool(rep.get("ok",False))})
        hits.append({"rule": r.get("name",""), "steps": local})
    _passport("rules_evaluate", {"when": when, "matched": len(hits)})
    return {"ok": True, "matched": len(hits), "report": hits}
# c=a+b