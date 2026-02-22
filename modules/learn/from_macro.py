# -*- coding: utf-8 -*-
"""
modules/learn/from_macro.py — obuchenie agenta iz makrosov (Arm→Disarm→Preview→Export→Apply).

Naznachenie:
- Zagruzit posledniy zapisannyy makros ili ukazannyy fayl.
- Ochistit shum (melkie dvizheniya, dubli khotkeev).
- Prevratit shagi v unifitsirovannye operatsii planov (op/op + args).
- Eksportirovat rezultat v pending_add.json (dlya ruchnogo ili avtomaticheskogo primeneniya).

MOSTY:
- Yavnyy: (Opyt ↔ Znanie) zapisannye deystviya → gotovye plan-shagi i shablony.
- Skrytyy #1: (Infoteoriya ↔ Obuchenie) chistka shumov snizhaet entropiyu opyta.
- Skrytyy #2: (Inzheneriya ↔ Sovmestimost) format sovpadaet s plan-builder'om.

ZEMNOY ABZATs:
Na praktike makros — eto JSON-zhurnal deystviy (click, type, hotkey…).  
Filtr stroit iz nego plan shagov, prigodnyy dlya povtornogo vosproizvedeniya ili sokhraneniya kak shablon.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import os, json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MACRO_DIR = os.path.join(os.environ.get("ESTER_ROOT", os.getcwd()), "data", "macro")
LAST_PATH = os.path.join(MACRO_DIR, "last_run.json")
PENDING_PATH = os.path.join(MACRO_DIR, "pending_add.json")

def _load_last() -> List[Dict[str, Any]]:
    if not os.path.exists(LAST_PATH):
        return []
    with open(LAST_PATH, "r", encoding="utf-8") as f:
        try: data=json.load(f)
        except Exception: data=[]
    return data if isinstance(data, list) else []

def _simplify(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out=[]
    seen=None
    for s in steps:
        op=s.get("op") or s.get("event") or ""
        if not op: 
            continue
        # obrezaem chastye povtory
        if op==seen:
            continue
        seen=op
        args={}
        if "text" in s: args["text"]=s["text"]
        if "bbox" in s: args.update(s["bbox"])
        out.append({"op":op,"args":args,"meta":{"hint":"from_macro","safety":"safe"}})
    return out

def preview(path: str | None = None) -> Dict[str, Any]:
    steps=_load_last() if not path else json.load(open(path,"r",encoding="utf-8"))
    clean=_simplify(steps)
    return {"ok": True, "count": len(clean), "plan": clean}

def export(path: str | None = None) -> Dict[str, Any]:
    data=preview(path)
    plan=data.get("plan",[])
    out={"exported_at": int(time.time()), "kind":"macro_plan", "items": plan}
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return {"ok": True, "saved": PENDING_PATH, "count": len(plan)}

def apply(path: str | None = None) -> Dict[str, Any]:
    data=preview(path)
    from modules.triggers.pending_import import try_apply
    res=try_apply(data.get("plan",[]))
    return {"ok": True, "applied": res}