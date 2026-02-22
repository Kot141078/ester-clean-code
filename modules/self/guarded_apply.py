# -*- coding: utf-8 -*-
"""
modules/self/guarded_apply.py — zaschischennoe primenenie pravok (A/B-sloty, testy, health, avto-otkat).

Mosty:
- Yavnyy: (Kod ↔ Resilience) dry→tests→apply→health→auto-rollback.
- Skrytyy #1: (Memory ↔ Profile) logiruem v pamyat rezultat i plan.
- Skrytyy #2: (Ostorozhnost ↔ Pilyuli/Byudzhet) vyzyvat cherez zaschischennuyu ruchku i CostFence.

Zemnoy abzats:
Kak khirurgiya po protokolu: snachala analiz, potom proba, zatem akkuratnyy shov i kontrol pulsa — esli plokho, otkat.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CODE_AB = (os.getenv("CODE_AB","A") or "A").upper()
B_MIRROR = os.getenv("CODE_B_MIRROR","data/forge/b_slot")
TEST_TIMEOUT = int(os.getenv("GUARDED_TEST_TIMEOUT","12") or "12")

def _mm_log(note: str, meta: Dict[str,Any]) -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm()
        upsert_with_passport(mm, note, meta, source="self://guarded_apply")
    except Exception:
        pass

def _cost_ok(amount: float=0.05) -> bool:
    try:
        from modules.ops.cost_fence import evaluate  # type: ignore
        return bool(evaluate("code", amount).get("allow", True))
    except Exception:
        return True

def _dry(changes: List[Dict[str,Any]]) -> Dict[str,Any]:
    from modules.self.forge import dry_run  # type: ignore
    return dry_run(changes or [])

def _apply(changes: List[Dict[str,Any]]) -> Dict[str,Any]:
    from modules.self.forge import apply  # type: ignore
    return apply(changes or [])

def _health() -> Dict[str,Any]:
    try:
        from modules.resilience.health import check  # type: ignore
        return check()
    except Exception:
        return {"ok": True}

def _rollback(paths: List[str]) -> Dict[str,Any]:
    try:
        from modules.resilience.rollback import rollback_paths  # type: ignore
        return rollback_paths(paths or [])
    except Exception:
        return {"ok": False, "error":"rollback_unavailable"}

def _bslot_path(path: str) -> str:
    # Parallelnoe zerkalo dlya B-slota: data/forge/b_slot/<abs-like>
    p=path.replace("..","").lstrip("/\\")
    return os.path.join(B_MIRROR, p)

def _ab_slot_changes(changes: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    if CODE_AB=="A":
        return changes
    # B-slot: zapisyvaem alternativnye versii v zerkalo (ne trogaem boevoy kod)
    out=[]
    for ch in changes or []:
        out.append({"path": _bslot_path(str(ch.get("path",""))), "content": str(ch.get("content",""))})
    return out

def _run_tests(tests: List[Dict[str,Any]]) -> Dict[str,Any]:
    if not tests: return {"ok": True, "results": []}
    results=[]
    ok_all=True
    for t in tests:
        kind=str(t.get("kind","python")).lower()
        if kind!="python":
            results.append({"ok": False, "error":"unsupported_kind"})
            ok_all=False
            continue
        code=str(t.get("code",""))
        try:
            from modules.sandbox.py_runner import run_py  # type: ignore
            rep=run_py(code, timeout_sec=TEST_TIMEOUT)
            results.append(rep)
            ok_all = ok_all and bool(rep.get("ok", False))
        except Exception as e:
            results.append({"ok": False, "stderr": str(e)})
            ok_all=False
    return {"ok": ok_all, "results": results}

def guarded_apply(changes: List[Dict[str,Any]], tests: List[Dict[str,Any]] | None = None, note: str = "") -> Dict[str,Any]:
    """
    changes: [{"path": "...", "content": "..."}]
    tests: [{"kind":"python","code":"..."}]
    """
    # Byudzhet
    if not _cost_ok(0.05):
        return {"ok": False, "error":"budget_reject"}

    plan=_dry(_ab_slot_changes(changes))
    trep=_run_tests(tests or [])
    if not trep.get("ok", False):
        _mm_log("Guarded apply tests failed", {"ok": False, "plan": plan, "slot": CODE_AB})
        return {"ok": False, "error":"tests_failed", "plan": plan, "tests": trep}

    applied=_apply(_ab_slot_changes(changes))
    if not applied.get("ok", False):
        _mm_log("Guarded apply failed to write", {"ok": False, "applied": applied, "slot": CODE_AB})
        return {"ok": False, "error":"apply_failed", "applied": applied}

    h=_health()
    if not h.get("ok", True) and CODE_AB=="A":
        # Otkat tolko esli pishem v boevoy A-slot
        paths=[c.get("path") for c in changes or []]
        rb=_rollback(paths)
        _mm_log("Guarded apply health failed -> rollback", {"ok": False, "health": h, "rollback": rb})
        return {"ok": False, "error":"health_failed_rolled_back", "health": h, "rollback": rb}

    meta={"ok": True, "slot": CODE_AB, "note": note, "plan": plan}
    _mm_log("Guarded apply success", meta)
    return {"ok": True, "slot": CODE_AB, "applied": applied, "health": h, "plan": plan, "tests": trep}
# c=a+b