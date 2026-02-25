# -*- coding: utf-8 -*-
"""modules/self/catalog.py - samoopisanie: routy, eksheny, A/B-sloty, cron-zadachi, ENV (whitelist).

Mosty:
- Yavnyy: (Prilozhenie ↔ Samopoznanie) vozvraschaet tekuschuyu kartu vozmozhnostey Ester.
- Skrytyy #1: (Memory ↔ Profile) gotov k logirovaniyu fakta samoobzora.
- Skrytyy #2: (UI ↔ Prozrachnost) daet dannym dlya ekranov “what ya umeyu” i “otkuda eto vzyalos”.

Zemnoy abzats:
Kak profile i tekhprofile odnovremenno: chto podklyucheno, kakie knopki dostupny, kakie rychagi stoyat v A/B, i kakie ENV vliyayut.

# c=a+b"""
from __future__ import annotations
import os, re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _env_whitelist()->List[str]:
    pat = os.getenv("SELF_ENV_ALLOW","").split(",")
    out=[]
    for k,v in os.environ.items():
        for p in pat:
            p=p.strip()
            if not p: continue
            if p.endswith("*"):
                if k.startswith(p[:-1]): out.append((k,v))
            elif k==p: out.append((k,v))
    out.sort(key=lambda x: x[0].lower())
    return [{"key":k,"value":v} for k,v in out]

def _routes(app)->List[Dict[str,Any]]:
    items=[]
    try:
        for r in app.url_map.iter_rules():
            items.append({
                "rule":   str(r),
                "methods": sorted(list(r.methods or [])),
                "endpoint": r.endpoint
            })
    except Exception:
        pass
    items.sort(key=lambda x: x["rule"])
    return items

def _actions()->List[Dict[str,Any]]:
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        rep=list_actions()
        if rep and rep.get("ok"): return rep.get("items") or []
    except Exception:
        pass
    return []

def _ab()->Dict[str,Any]:
    try:
        from modules.runtime.ab_slots import status  # type: ignore
        rep=status()
        if rep and rep.get("ok"): return rep
    except Exception:
        pass
    return {"ok": True, "components": {}}

def _cron()->Dict[str,Any]:
    try:
        from modules.cron.scheduler import list_tasks, status  # type: ignore
        st=status() if callable(status) else {}
        lt=list_tasks() if callable(list_tasks) else {}
        return {"status": st, "tasks": lt.get("items",[])}
    except Exception:
        return {"status": {"ok": False}, "tasks":[]}

def catalog(app)->Dict[str,Any]:
    return {
        "ok": True,
        "routes": _routes(app),
        "actions": _actions(),
        "ab": _ab(),
        "cron": _cron(),
        "env": _env_whitelist()
    }

def capabilities(app)->Dict[str,Any]:
    cat=catalog(app)
    # short squeeze: quantity and key groups
    return {
        "ok": True,
        "counts": {
            "routes": len(cat.get("routes",[])),
            "actions": len(cat.get("actions",[])),
            "ab_components": len((cat.get("ab") or {}).get("components",{})),
            "cron_tasks": len((cat.get("cron") or {}).get("tasks",[])),
            "env_keys": len(cat.get("env",[]))
        },
        "highlights": {
            "has_garage": any("/garage/" in r["rule"] for r in cat.get("routes",[])),
            "has_passport": any(a["name"].startswith("mem.passport") for a in cat.get("actions",[])),
            "has_selfevo": any(a["name"].startswith("workbench.") for a in cat.get("actions",[]))
        }
    }
# c=a+b