# -*- coding: utf-8 -*-
"""modules/self/capmap.py - “karta sposobnostey”: ​​route, eksheny, ENV, artefakty.

Mosty:
- Yavnyy: (Self-Introspection ↔ UI) edinaya panel “what ya umeyu”.
- Skrytyy #1: (Profile ↔ Prozrachnost) snimki karty mozhno shtampovat dlya istorii.
- Skrytyy #2: (Thinking/Rules ↔ Plan) karta — opora pri samostoyatelnykh resheniyakh.

Zemnoy abzats:
Kak pamyatka inzhenera: spisok instrumentov pod rukoy, where oni lezhat i kak ikh zovut. Ne teryaemsya v bolshom proekte.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PREFIXES=[p for p in (os.getenv("CAPMAP_ENV_PREFIXES","").split(",")) if p]

def build(current_app)->Dict[str,Any]:
    # 1) Routy
    routes=[]
    try:
        for r in current_app.url_map.iter_rules():
            methods=sorted(m for m in r.methods if m in ("GET","POST","PUT","DELETE","PATCH"))
            routes.append({"rule": str(r), "methods": methods, "endpoint": r.endpoint})
    except Exception:
        pass
    routes=sorted(routes, key=lambda x: x["rule"])

    # 2) Eksheny
    actions=[]
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        for a in list_actions():
            actions.append({"name": a["name"], "inputs": a.get("inputs",{}), "weight": a.get("weight",1)})
    except Exception:
        pass

    # 3) ENV po prefiksam
    env={}
    for k,v in os.environ.items():
        if any(k.startswith(p) for p in PREFIXES):
            env[k]=v

    # 4) Artefakty (profile/bandly/portfolio)
    art={}
    def _safe_size(path: str)->int:
        try:
            if os.path.isdir(path):
                s=0
                for b,_,ns in os.walk(path):
                    for n in ns:
                        s+=os.stat(os.path.join(b,n)).st_size
                return s
            return os.stat(path).st_size if os.path.isfile(path) else 0
        except Exception: return 0
    art["passport_log"]= {"path": os.getenv("PASSPORT_LOG","data/passport/log.jsonl"), "size": _safe_size(os.getenv("PASSPORT_LOG","data/passport/log.jsonl"))}
    art["portfolio"]= {"path": os.getenv("PORTFOLIO_DIR","data/portfolio"), "size": _safe_size(os.getenv("PORTFOLIO_DIR","data/portfolio"))}
    art["slots"]= {"path": os.getenv("RUNTIME_SLOTS_DIR","slots"), "size": _safe_size(os.getenv("RUNTIME_SLOTS_DIR","slots"))}

    snap={"t": int(time.time()), "routes": routes, "actions": actions, "env": env, "artifacts": art}
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("capmap_snapshot", {"routes": len(routes), "actions": len(actions)}, "self://capmap")
    except Exception:
        pass
    return {"ok": True, "capmap": snap}
# c=a+b