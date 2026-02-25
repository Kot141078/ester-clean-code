# -*- coding: utf-8 -*-
"""modules/sys/autoreg.py - avto-skan i registratsiya novykh moduley (routes/*.py) s proverkoy doveriya.

Mosty:
- Yavnyy: (Skaner ↔ Flask) ischem fayly s funktsiey register(app) i podklyuchaem ikh.
- Skrytyy #1: (CodeTrust ↔ Bezopasnost) ne registriruem neznakomye fayly v strict-rezhime.
- Skrytyy #2: (Volya ↔ Planirovschik) mozhno zapuskat taymerom/sobytiem i v dry-run (AB-slot).

Zemnoy abzats:
Kak master-sborschik: nashel novye details, sveril katalozhnyy number (khesh), prikrutil k sisteme.

# c=a+b"""
from __future__ import annotations
import os, json, glob, importlib.util, inspect
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB   = (os.getenv("AUTOREG_AB","A") or "A").upper()
DB   = os.getenv("AUTOREG_DB","data/sys/autoreg.json")
SCNV = os.getenv("AUTOREG_SCAN","routes/*.py")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"seen":{}, "registered":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _iter_files(patterns: List[str])->List[str]:
    out=[]
    for p in patterns:
        out.extend(glob.glob(p.strip()))
    # unikaliziruem, sortiruem
    return sorted(list(set(out)))

def _try_import(path: str):
    spec=importlib.util.spec_from_file_location(os.path.basename(path).replace(".py",""), path)
    if not spec or not spec.loader: return None
    mod=importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore
        return mod
    except Exception:
        return None

def tick(app, scan_patterns: List[str]|None=None)->Dict[str,Any]:
    """Returns a report: what was found, what was registered, what was rejected."""
    from modules.sys.codetrust import is_trusted, quarantine  # type: ignore
    pats=scan_patterns or [x for x in SCNV.split(",") if x.strip()]
    files=_iter_files(pats)
    j=_load()
    found=[]; registered=[]; rejected=[]
    for path in files:
        found.append(path)
        if not is_trusted(path):
            quarantine(path, "untrusted_file")
            rejected.append({"path": path, "reason":"untrusted"})
            continue
        mod=_try_import(path)
        if not mod or not hasattr(mod, "register"):
            rejected.append({"path": path, "reason":"no_register"})
            continue
        func=getattr(mod,"register")
        if not inspect.isfunction(func):
            rejected.append({"path": path, "reason":"bad_register"})
            continue
        if AB=="A":
            try:
                func(app)  # register(app)
                registered.append(path)
                if path not in j["registered"]:
                    j["registered"].append(path)
            except Exception as e:
                rejected.append({"path": path, "reason": f"register_fail:{e}"})
        else:
            # dry-run: just mark “seen”
            pass
        j["seen"][path]=True
    _save(j)
    _passport("autoreg_tick", {"found": len(found), "registered": len(registered), "rejected": len(rejected), "AB": AB})
    return {"ok": True, "AB": AB, "found": found, "registered": registered, "rejected": rejected}

def _passport(note:str, meta:Dict[str,Any])->None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, note, meta, source="sys://autoreg")
    except Exception:
        pass
# c=a+b