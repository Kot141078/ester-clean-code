# -*- coding: utf-8 -*-
"""modules/discovery/loader.py - avto-podkhvat routes/actions, fon-scanner, zhurnal.

Mosty:
- Yavnyy: (App Bootstrap ↔ Routes/Actions) tsentralizovannaya registratsiya moduley.
- Skrytyy #1: (Passport ↔ Prozrachnost) vse skany/registratsii shtampuyutsya.
- Skrytyy #2: (CapMap/Hub ↔ Navigatsiya) status available dlya UI i planirovschika.

Zemnoy abzats:
Eto “dispetcher tsekha”: on obkhodit masterskuyu, nakhodit novye stanki (moduli), podklyuchaet k seti (Flask/registrator ekshenov) i otmechaet v zhurnale.

# c=a+b"""
from __future__ import annotations
import os, sys, time, importlib, threading, pkgutil, traceback
from types import ModuleType
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PKG_ROUTES=os.getenv("DISCOVERY_ROUTES_PKG","routes")
PKG_ACTIONS=os.getenv("DISCOVERY_ACTIONS_PKG","modules.thinking")
INTERVAL=int(os.getenv("DISCOVERY_INTERVAL_SEC","60") or "60")
AUTORUN=(os.getenv("DISCOVERY_AUTORUN","true").lower()=="true")

_state={
    "last_scan": 0,
    "last_register": 0,
    "scan_count": 0,
    "register_count": 0,
    "autorun": AUTORUN,
    "interval_sec": INTERVAL,
    "errors": [],
    "found": []  # [{'name':str,'kind':'route|action'}]
}
_reg={"routes": set(), "actions": set()}
_app=None  # late-bound Flask app

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

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "boot://discover")
    except Exception:
        pass

def attach_app(app):
    global _app
    _app=app

def _iter_pkg(pkg_name: str)->List[str]:
    mods=[]
    try:
        pkg=importlib.import_module(pkg_name)
        pkg_path=getattr(pkg, "__path__", None)
        if not pkg_path: return []
        for it in pkgutil.iter_modules(pkg_path):
            full=f"{pkg_name}.{it.name}"
            mods.append(full)
    except Exception as e:
        _state["errors"].append(f"iter_pkg:{pkg_name}:{e}")
    return mods

def scan()->Dict[str,Any]:
    found=[]
    # routes
    for m in _iter_pkg(PKG_ROUTES):
        if m.endswith("_routes") or ".routes" in m or m.startswith("routes."):
            found.append({"name": m, "kind":"route"})
    # actions
    for m in _iter_pkg(PKG_ACTIONS):
        if m.endswith(".actions") or ".actions_" in m or m.startswith("modules.thinking.actions"):
            found.append({"name": m, "kind":"action"})
    # uniq
    seen=set(); uniq=[]
    for x in found:
        if x["name"] in seen: continue
        seen.add(x["name"]); uniq.append(x)
    _state["found"]=uniq
    _state["last_scan"]=int(time.time())
    _state["scan_count"]+=1
    _passport("discover_scan", {"found": len(uniq)})
    try:
        _mirror_background_event(
            f"[DISCOVERY_SCAN] found={len(uniq)}",
            "discovery_loader",
            "scan",
        )
    except Exception:
        pass
    return {"ok": True, "found": uniq, "scan_count": _state["scan_count"]}

def _register_route_module(mod: ModuleType)->bool:
    try:
        if hasattr(mod,"register") and callable(mod.register) and _app is not None:
            mod.register(_app)  # type: ignore
        return True
    except Exception as e:
        _state["errors"].append(f"register_route:{mod.__name__}:{e}")
        return False

def _import_and_register(name: str, kind: str)->bool:
    mod=None
    try:
        mod=importlib.import_module(name)
    except Exception as e:
        _state["errors"].append(f"import:{name}:{e}")
        return False
    if kind=="route":
        return _register_route_module(mod)
    else:
        # actions - just import (they register themselves through registers)
        return True

def register(modules: List[str])->Dict[str,Any]:
    ok=0; err=0
    for name in modules or []:
        kind="route" if name.startswith(PKG_ROUTES) else "action"
        # skip already registered
        bag=_reg["routes"] if kind=="route" else _reg["actions"]
        if name in bag: 
            continue
        if _import_and_register(name, kind):
            bag.add(name); ok+=1
        else:
            err+=1
    _state["last_register"]=int(time.time())
    _state["register_count"]+=ok
    _passport("discover_register", {"ok": ok, "err": err})
    try:
        _mirror_background_event(
            f"[DISCOVERY_REGISTER] ok={ok} err={err}",
            "discovery_loader",
            "register",
        )
    except Exception:
        pass
    return {"ok": True, "registered": ok, "errors": err, "routes": len(_reg["routes"]), "actions": len(_reg["actions"])}

def status()->Dict[str,Any]:
    return {"ok": True, "state": dict(_state), "routes": sorted(list(_reg["routes"])), "actions": sorted(list(_reg["actions"]))}

def autorun(enable: bool|None=None, interval_sec: int|None=None)->Dict[str,Any]:
    if enable is not None:
        _state["autorun"]=bool(enable)
    if interval_sec:
        _state["interval_sec"]=int(interval_sec)
    return status()

def _loop():
    while True:
        if not _state["autorun"]:
            time.sleep(1); continue
        try:
            sc=scan()
            names=[x["name"] for x in sc.get("found",[])]
            register(names)
        except Exception as e:
            _state["errors"].append(f"loop:{e}")
            try:
                _mirror_background_event(
                    f"[DISCOVERY_LOOP_ERROR] {e}",
                    "discovery_loader",
                    "loop_error",
                )
            except Exception:
                pass
        time.sleep(max(5, int(_state["interval_sec"])))

# launching a background thread (officially: “enabled by default”, described in the header)
def _ensure_thread():
    t=threading.Thread(target=_loop, name="discovery_loop", daemon=True)
    t.start()
    _passport("discover_thread", {"started": True})
    try:
        _mirror_background_event(
            "[DISCOVERY_THREAD_START]",
            "discovery_loader",
            "thread_start",
        )
    except Exception:
        pass

# Avtozapusk pri importe modulya
if AUTORUN:
    _ensure_thread()
# c=a+b