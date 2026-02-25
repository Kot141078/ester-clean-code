# -*- coding: utf-8 -*-
"""modules/discover/registry.py - avto-diskaver i bezopasnaya registratsiya moduley s register(app).

Mosty:
- Yavnyy: (FS ↔ Flask) nakhodit python-fayly s routami i podklyuchaet ikh k prilozheniyu.
- Skrytyy #1: (Profile ↔ Prozrachnost) kazhdyy udachnyy/neudachnyy import shtampuetsya.
- Skrytyy #2: (Cron/Volya ↔ Avtonomnost) mozhno vyzyvat reskan po raspisaniyu ili iz payplayna.

Zemnoy abzats:
This is “inventarizatsiya i sborschik”: probezhal po katalogam, nashel novye routy, akkuratno podklyuchil - bez ruchnogo pravki app.py.

# c=a+b"""
from __future__ import annotations
import os, json, time, glob, importlib, threading, inspect
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("DISCOVER_DB","data/discover/registry.json")
GLOBS = [g.strip() for g in (os.getenv("DISCOVER_GLOBS","routes/*.py,routes/*_routes.py,routes/**/**_routes.py,modules/**/routes_*.py") or "").split(",") if g.strip()]
ALLOW_PREFIXES = [p.strip() for p in (os.getenv("DISCOVER_ALLOW_PREFIXES","routes.,modules.") or "").split(",") if p.strip()]
MAX_IMPORT_SEC = int(os.getenv("DISCOVER_MAX_IMPORT_SEC","10") or "10")

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

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"seen":{}, "registered":{}}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _to_modname(py_path: str)->str:
    # modules/x/y.py -> modules.x.y ; routes/x_routes.py -> routes.x_routes
    rel=py_path.replace("\\","/").lstrip("./")
    if rel.endswith(".py"): rel=rel[:-3]
    return rel.replace("/", ".")

def _allowed_mod(mod: str)->bool:
    return any(mod.startswith(p) for p in ALLOW_PREFIXES)

def scan()->Dict[str,Any]:
    seen={}
    for g in GLOBS:
        for p in glob.glob(g, recursive=True):
            if os.path.basename(p).startswith("_"): 
                continue
            mod=_to_modname(p)
            if not _allowed_mod(mod): 
                continue
            seen[mod]={"path": p}
    j=_load(); j["seen"]=seen; _save(j)
    try:
        _mirror_background_event(
            f"[DISCOVER_SCAN] modules={len(seen)}",
            "discover_registry",
            "scan",
        )
    except Exception:
        pass
    return {"ok": True, "modules": sorted(list(seen.keys()))}

def _passport(note: str, meta: Dict[str,Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "discover://loader")
    except Exception:
        pass

def _import_with_timeout(modname: str):
    out={"obj": None, "err": None}
    def _target():
        try:
            out["obj"]= importlib.import_module(modname)
        except Exception as e:
            out["err"]= e
    th=threading.Thread(target=_target, daemon=True); th.start(); th.join(MAX_IMPORT_SEC)
    if th.is_alive():
        return None, TimeoutError(f"import_timeout:{modname}")
    return out["obj"], out["err"]

def register(mods: List[str])->Dict[str,Any]:
    from flask import current_app
    reg_ok=[]; reg_err=[]
    j=_load(); regs=j.get("registered") or {}
    for m in mods or []:
        if not _allowed_mod(m):
            reg_err.append({"module": m, "error":"not_allowed"}); continue
        obj, err=_import_with_timeout(m)
        if err or obj is None:
            reg_err.append({"module": m, "error": str(err or "import_failed")})
            _passport("discover_import_fail", {"module": m, "err": str(err) if err else "none"})
            try:
                _mirror_background_event(
                    f"[DISCOVER_IMPORT_FAIL] {m} err={err}",
                    "discover_registry",
                    "import_fail",
                )
            except Exception:
                pass
            continue
        fn=getattr(obj, "register", None)
        if not callable(fn):
            reg_err.append({"module": m, "error":"no_register(app)"})
            _passport("discover_no_register", {"module": m})
            try:
                _mirror_background_event(
                    f"[DISCOVER_NO_REGISTER] {m}",
                    "discover_registry",
                    "no_register",
                )
            except Exception:
                pass
            continue
        try:
            fn(current_app)   # type: ignore
            regs[m]={"t": int(time.time())}
            reg_ok.append(m)
            _passport("discover_registered", {"module": m})
            try:
                _mirror_background_event(
                    f"[DISCOVER_REGISTERED] {m}",
                    "discover_registry",
                    "registered",
                )
            except Exception:
                pass
        except Exception as e:
            reg_err.append({"module": m, "error": f"register_fail:{e}"})
            _passport("discover_register_fail", {"module": m, "err": str(e)})
            try:
                _mirror_background_event(
                    f"[DISCOVER_REGISTER_FAIL] {m} err={e}",
                    "discover_registry",
                    "register_fail",
                )
            except Exception:
                pass
    j["registered"]=regs; _save(j)
    return {"ok": True, "registered": reg_ok, "errors": reg_err, "count": len(reg_ok)}

def status()->Dict[str,Any]:
    j=_load()
    return {"ok": True, "seen": j.get("seen",{}), "registered": j.get("registered",{})}

def refresh(autoreg: bool=False)->Dict[str,Any]:
    sc=scan()
    regs=[]
    errs=[]
    if autoreg:
        mods=sc.get("modules") or []
        # we connect only those that do not exist yet
        old=set((_load().get("registered") or {}).keys())
        new=[m for m in mods if m not in old]
        if new:
            rep=register(new)
            regs=rep.get("registered") or []
            errs=rep.get("errors") or []
    return {"ok": True, "scan": sc, "auto_registered": regs, "errors": errs}
# c=a+b