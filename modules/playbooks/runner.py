# -*- coding: utf-8 -*-
"""
modules/playbooks/runner.py — kaskadnye stsenarii (playbooks) poverkh reestra deystviy.

Mosty:
- Yavnyy: (Myshlenie ↔ Ispolnenie) deklarativno opisyvaem shagi {kind,args}.
- Skrytyy #1: (Ekonomika ↔ Ogranicheniya) uvazhaem CostFence/limity.
- Skrytyy #2: (Memory ↔ Avtonomiya) legko skladyvat rezultaty v pamyat/ledger.

Zemnoy abzats:
«Poymat rybu» — ne raz: oformlyaem povtoryaemye tsepochki deystviy, chtoby Ester sama ikh zapuskala.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PLAYBOOKS_DIR = os.getenv("PLAYBOOKS_DIR","data/playbooks")

def _parse(data: str, content_type: str | None) -> Dict[str,Any]:
    if content_type and "yaml" in content_type:
        try:
            import yaml  # type: ignore
            return yaml.safe_load(data)
        except Exception:
            pass
    try:
        return json.loads(data)
    except Exception:
        # fallback minimalnyy YAML (klyuch:znachenie i massivy - best-effort)
        lines=[l.rstrip() for l in data.splitlines() if l.strip()]
        name="pb"; steps=[]
        for l in lines:
            if l.strip().startswith("-"):
                steps.append({"kind":"echo","args":{"text": l.strip()[1:].strip()}})
        return {"name": name, "steps": steps}

def _cost_ok(cat: str, amount: float) -> bool:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        return bool(evaluate(cat, amount).get("allow"))
    except Exception:
        return True

def _invoke_action(kind: str, args: Dict[str,Any]) -> Dict[str,Any]:
    try:
        from modules.thinking.action_registry import invoke  # type: ignore
        rep = invoke(kind, args or {})
        if not isinstance(rep, dict): rep={"ok": True, "result": rep}
        return rep
    except Exception as e:
        # Bazovye vstroennye deystviya
        if kind=="echo":
            return {"ok": True, "text": str(args.get("text",""))}
        if kind=="memory.upsert":
            try:
                from services.mm_access import get_mm  # type: ignore
                mm=get_mm(); mm.upsert({"text": str(args.get("text","")), "meta": {"from":"playbook"}})
                return {"ok": True, "saved": True}
            except Exception as ee:
                return {"ok": False, "error": f"memory:{ee}"}
        return {"ok": False, "error": f"unknown_action:{kind}"}

def validate(obj: Dict[str,Any]) -> Dict[str,Any]:
    errs=[]
    if not isinstance(obj.get("steps"), list) or not obj["steps"]:
        errs.append("steps: empty")
    for i,st in enumerate(obj.get("steps",[])):
        if "kind" not in st:
            errs.append(f"step[{i}]: no kind")
    return {"ok": len(errs)==0, "errors": errs}

def run(obj: Dict[str,Any]) -> Dict[str,Any]:
    name=str(obj.get("name","pb"))
    limits=obj.get("limits") or {}
    results=[]
    for st in obj.get("steps",[]):
        k=st.get("kind",""); a=st.get("args") or {}
        # prostaya otsenka stoimosti (esli ukazana)
        cat=str(st.get("cost_cat","llm")); amt=float(st.get("cost",0.0))
        if amt>0.0 and not _cost_ok(cat, amt):
            results.append({"ok": False, "step": k, "error":"cost_exceeded"}); break
        rep=_invoke_action(k, a)
        results.append({"step": k, **rep})
        if not rep.get("ok"):
            break
    return {"ok": all(r.get("ok",True) for r in results), "name": name, "results": results}
# c=a+b