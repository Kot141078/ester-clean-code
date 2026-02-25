# -*- coding: utf-8 -*-
"""modules/thinking/action_invoker.py - bezopasnyy invoker ekshenov s WIP/taymautom i auditom.

Mosty:
- Yavnyy: (Reestr deystviy ↔ Ispolnitel) tsentralizovannyy vyzov ekshenov s kontrolem parametrov i vremeni.
- Skrytyy #1: (Memory ↔ Profile) uspeshnye vyzovy mozhno zhurnalirovat “profileom”.
- Skrytyy #2: (RBAC/Politiki ↔ Ostorozhnost) syuda legko vstavit dop.proverki (quota/roles).

Zemnoy abzats:
Kak “dispetcher v tsekhe”: puskaet zadachi po odnoy dveri, sledit za peregruzkoy i rubit po taymautu - chtoby tsekh ne vstal.

# c=a+b"""
from __future__ import annotations
import os, json, time, threading
from typing import Any, Dict, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAX_WIP = int(os.getenv("ACTIONS_MAX_WIP","8") or "8")
TIMEOUT = int(os.getenv("ACTION_TIMEOUT_SEC","30") or "30")
AUDIT_DB = os.getenv("ACTION_INVOKE_AUDIT_DB","data/thinking/actions_audit.json")

_WIP_LOCK = threading.RLock()
_WIP_NOW  = 0
_STATS = {"ok":0,"fail":0,"timeout":0,"last":None}

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _ensure_audit():
    os.makedirs(os.path.dirname(AUDIT_DB), exist_ok=True)
    if not os.path.isfile(AUDIT_DB):
        json.dump({"calls":[]}, open(AUDIT_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _audit(note: str, meta: Dict[str,Any]):
    _ensure_audit()
    j=json.load(open(AUDIT_DB,"r",encoding="utf-8"))
    j["calls"].append({"t":int(time.time()), "note":note, "meta":meta})
    json.dump(j, open(AUDIT_DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _list_actions()->Dict[str,Any]:
    # Berem iz suschestvuyuschego reestra
    try:
        from modules.thinking.action_registry import list_actions  # type: ignore
        rep=list_actions(); 
        if rep and rep.get("ok"): return rep
    except Exception:
        pass
    return {"ok": True, "items": []}

def _get_runner(name: str):
    """Pytaemsya poluchit ispolnyaemuyu funktsiyu ekshena iz reestra.
    Ozhidaemyy kontrakt reestra: list_actions() -> items[] s polem "name" i "runner".
    Esli runner net - akkuratno padaem."""
    rep=_list_actions()
    for it in rep.get("items",[]):
        if it.get("name")==name:
            return it.get("runner") or it.get("callable") or None
    return None

def _validate_schema(item: Dict[str,Any], args: Dict[str,Any])->Tuple[bool,str]:
    schema = item.get("schema_in") or {}
    # The simplest check: keys and types (page|number|pain|object|sheet)
    typemap={"str":str,"number":(int,float),"bool":bool,"object":dict,"list":list}
    for k, t in (schema.items() if isinstance(schema, dict) else []):
        if k not in args: 
            # allow optional fields - strict mode can be enabled later
            continue
        want = typemap.get(str(t))
        if want and not isinstance(args[k], want):
            return False, f"bad_type:{k}"
    return True, ""

def list_for_api()->Dict[str,Any]:
    rep=_list_actions()
    items=[]
    for it in rep.get("items",[]):
        items.append({
            "name": it.get("name"),
            "cost": it.get("cost"),
            "schema_in": it.get("schema_in"),
            "schema_out": it.get("schema_out")
        })
    return {"ok": True, "items": items}

def stats()->Dict[str,Any]:
    with _WIP_LOCK:
        return {"ok": True, "wip": _WIP_NOW, "max_wip": MAX_WIP, "timeouts_sec": TIMEOUT, "counters": dict(_STATS)}

def invoke(name: str, args: Dict[str,Any])->Dict[str,Any]:
    # 1) Poluchim opisanie i runner
    rep=_list_actions()
    item=None
    for it in rep.get("items",[]):
        if it.get("name")==name:
            item=it; break
    if not item:
        _audit("act_not_found", {"name":name})
        try:
            _mirror_background_event(
                f"[ACTION_NOT_FOUND] {name}",
                "action_invoker",
                "not_found",
            )
        except Exception:
            pass
        return {"ok": False, "error":"action_not_found"}

    ok, err=_validate_schema(item, args or {})
    if not ok:
        _audit("act_schema_fail", {"name":name,"err":err})
        try:
            _mirror_background_event(
                f"[ACTION_SCHEMA_FAIL] {name} err={err}",
                "action_invoker",
                "schema_fail",
            )
        except Exception:
            pass
        return {"ok": False, "error": err or "schema_mismatch"}

    runner=_get_runner(name)
    if runner is None or not callable(runner):
        _audit("act_no_runner", {"name":name})
        try:
            _mirror_background_event(
                f"[ACTION_NO_RUNNER] {name}",
                "action_invoker",
                "no_runner",
            )
        except Exception:
            pass
        return {"ok": False, "error":"runner_unavailable"}

    # 2) WIP/taymaut
    with _WIP_LOCK:
        global _WIP_NOW
        if _WIP_NOW >= MAX_WIP:
            _audit("act_overload", {"name":name,"wip":_WIP_NOW})
            try:
                _mirror_background_event(
                    f"[ACTION_OVERLOAD] {name} wip={_WIP_NOW}",
                    "action_invoker",
                    "overload",
                )
            except Exception:
                pass
            return {"ok": False, "error":"overload"}
        _WIP_NOW += 1
    try:
        out_box={}
        exc_box={}
        def _target():
            try:
                out_box["rep"]= runner(args or {})
            except Exception as e:
                exc_box["e"]=e
        th=threading.Thread(target=_target, daemon=True)
        th.start(); th.join(TIMEOUT)
        if th.is_alive():
            _STATS["timeout"]+=1
            _audit("act_timeout", {"name":name,"timeout_sec":TIMEOUT})
            try:
                _mirror_background_event(
                    f"[ACTION_TIMEOUT] {name}",
                    "action_invoker",
                    "timeout",
                )
            except Exception:
                pass
            return {"ok": False, "error":"timeout"}
        if "e" in exc_box:
            _STATS["fail"]+=1
            _audit("act_fail", {"name":name,"err": str(exc_box["e"])})
            try:
                _mirror_background_event(
                    f"[ACTION_FAIL] {name} err={exc_box['e']}",
                    "action_invoker",
                    "fail",
                )
            except Exception:
                pass
            return {"ok": False, "error": f"exception:{exc_box['e']}"}
        _STATS["ok"]+=1; _STATS["last"]=int(time.time())
        _audit("act_ok", {"name":name})
        try:
            _mirror_background_event(
                f"[ACTION_OK] {name}",
                "action_invoker",
                "ok",
            )
        except Exception:
            pass
        return out_box.get("rep") or {"ok": True}
    finally:
        with _WIP_LOCK:
            _WIP_NOW = max(0, _WIP_NOW-1)
# c=a+b