# -*- coding: utf-8 -*-
"""modules/selfmap/introspect.py - samokarta sposobnostey: route, eksheny, moduli, env.

Mosty:
- Yavnyy: (Prilozhenie ↔ Soznanie) edinyy JSON-portret “who ya i chto umeyu.”
- Skrytyy #1: (AutoDiscover ↔ Prozrachnost) ispolzuem reestr scanera moduley.
- Skrytyy #2: (Thinking Registry ↔ Navigatsiya) snimaem spisok dostupnykh ekshenov “voli”.

Zemnoy abzats:
Kak tablichka pod kapotom: kakie uzly podklyucheny, kakie rychagi est, kakie lampochki goryat - bystro ponyat sostoyanie.

# c=a+b"""
from __future__ import annotations
import os, json, time, inspect, pkgutil, importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

REG_DB=os.getenv("SELFMAP_DB","data/discover/registry.json")

def _read_json(path: str)->dict:
    try:
        return json.load(open(path,"r",encoding="utf-8"))
    except Exception:
        return {}

def _routes_from_sources(modnames):
    routes=[]
    for m in modnames:
        try:
            mod=importlib.import_module(m)
            import inspect as _i, re
            src=_i.getsource(mod)
            for r in re.finditer(r'@bp\.route\(\s*"(.*?)"\s*,\s*methods=\[(.*?)\]\s*\)', src):
                path=r.group(1); methods=",".join([x.strip().strip('"\'') for x in r.group(2).split(",")])
                routes.append({"module": m, "path": path, "methods": methods})
        except Exception:
            continue
    return routes

def _action_list():
    # let's try to pull it out of the action registry if it provides introspection
    acts=[]
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        acts = list_actions() or []
    except Exception:
        # evristika: oboyti izvestnye pakety i poiskat register("name",
        try:
            for _, mname, _ in pkgutil.walk_packages(["modules/thinking"], prefix="modules.thinking."):
                try:
                    m=importlib.import_module(mname)
                    import inspect as _i, re
                    src=_i.getsource(m)
                    for reg in re.finditer(r'register\(\s*"([^"]+)"', src):
                        acts.append({"name": reg.group(1)})
                except Exception:
                    continue
        except Exception:
            pass
    # normalizuem
    out=[]
    for a in acts:
        if isinstance(a, dict) and "name" in a: out.append({"name": a["name"]})
        elif isinstance(a, str): out.append({"name": a})
    # unikaliziruem
    seen=set(); uniq=[]
    for x in out:
        n=x["name"]
        if n in seen: continue
        seen.add(n); uniq.append(x)
    return uniq

def snapshot()->dict:
    reg=_read_json(REG_DB)
    seen=list((reg.get("seen") or {}).keys())
    registered=list((reg.get("registered") or {}).keys())
    routes=_routes_from_sources(sorted(set(seen+registered)))
    env={
        "APP_TITLE": os.getenv("APP_TITLE","Ester Control Panel"),
        "RBAC_REQUIRED": os.getenv("RBAC_REQUIRED","true"),
        "MEDIA_ALLOW_NETWORK": os.getenv("MEDIA_ALLOW_NETWORK","true"),
        "DISCOVER_AUTOREG": os.getenv("DISCOVER_AUTOREG","false")
    }
    acts=_action_list()
    info={
        "t": int(time.time()),
        "modules_seen": len(seen),
        "modules_registered": len(registered),
        "routes": routes,
        "actions": acts,
        "env": env
    }
    # profile (best-effort)
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("selfmap_snapshot", {"routes": len(routes), "actions": len(acts)}, "self://map")
    except Exception:
        pass
    return {"ok": True, "info": info}
# c=a+b