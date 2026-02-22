# -*- coding: utf-8 -*-
"""
modules/mm/guard.py — monitoring i myagkaya zaschita dostupa k pamyati (get_mm).

Mosty:
- Yavnyy: (Memory ↔ Audit) schitaet vyzovy get_mm i pozvolyaet pomechat «obkhody».
- Skrytyy #1: (Linter ↔ Kodovaya baza) skript-skaner mozhet flagat podozreniya.
- Skrytyy #2: (Politiki ↔ Ostorozhnost) optsionalnyy enforce-blok po maskam moduley.

Zemnoy abzats:
Schetchik u dveri sklada: kto beret klyuchi ot pamyati i ne pytaetsya li kto-to vlezt cherez chernyy khod.

# c=a+b
"""
from __future__ import annotations
import os, json, time, traceback
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("MM_AUDIT_DB","data/mem/mm_audit.json")
ENFORCE=(os.getenv("MM_GUARD_ENFORCE","false").lower()=="true")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"calls":0,"by_module":{},"flags":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def patch_get_mm()->bool:
    """
    Oborachivaet services.mm_access.get_mm — bez izmeneniya signatur.
    """
    try:
        import services.mm_access as mma  # type: ignore
    except Exception:
        return False

    if hasattr(mma, "_ESTER_MM_PATCHED"):  # uzhe patchen
        return True

    orig = getattr(mma, "get_mm", None)
    if not callable(orig): return False

    def wrapped(*a, **kw):
        # audit
        j=_load(); j["calls"]=int(j.get("calls",0))+1
        # opredelim modul-vyzyvatel (stek)
        caller="unknown"
        try:
            import inspect
            for fr in inspect.stack()[1:5]:
                m=fr.frame.f_globals.get("__name__")
                if m and not m.startswith("services.mm_access"):
                    caller=m; break
        except Exception:
            caller="unknown"
        by=j.get("by_module") or {}
        by[caller]= int(by.get(caller,0))+1
        j["by_module"]=by; _save(j)

        # pri neobkhodimosti mozhno vvesti zaprety (ENFORCE) — po belomu spisku moduley
        # seychas — monitoring bez zapretov
        return orig(*a, **kw)

    setattr(mma, "get_mm", wrapped)
    setattr(mma, "_ESTER_MM_PATCHED", True)
    return True

def status()->Dict[str,Any]:
    j=_load(); return {"ok": True, "calls": j.get("calls",0), "by_module": j.get("by_module",{}), "flags": j.get("flags",[])}

def flag_bypass(path: str, reason: str)->Dict[str,Any]:
    j=_load(); fl=j.get("flags") or []
    fl.append({"t": int(time.time()), "path": path, "reason": reason})
    j["flags"]=fl; _save(j)
    return {"ok": True, "flagged": {"path": path, "reason": reason}}

_BOOTSTRAP: Dict[str, Any] = {"patched": False, "error": None, "ts": int(time.time())}

def bootstrap_patch() -> Dict[str, Any]:
    _BOOTSTRAP["ts"] = int(time.time())
    try:
        _BOOTSTRAP["patched"] = bool(patch_get_mm())
        _BOOTSTRAP["error"] = None
    except Exception as exc:
        _BOOTSTRAP["patched"] = False
        _BOOTSTRAP["error"] = f"{exc.__class__.__name__}: {exc}"
        try:
            flag_bypass("modules/mm/guard.py", f"patch_get_mm_failed:{_BOOTSTRAP['error']}")
        except Exception:
            traceback.print_exc()
    return dict(_BOOTSTRAP)

# Patchim pri importe modulya (myagko) i sokhranyaem status.
bootstrap_patch()
# c=a+b
