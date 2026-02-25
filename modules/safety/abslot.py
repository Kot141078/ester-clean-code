# -*- coding: utf-8 -*-
"""modules/safety/abslot.py - A/B-sloty s avto-otkatom: bezopasnoe pereklyuchenie logiki bez regressiy.

Mosty:
- Yavnyy: (Biznes-logika ↔ Bezopasnost) odin helper dlya vybora realizatsii A|B.
- Skrytyy #1: (Profile ↔ Prozrachnost) oshibki B i pereklyucheniya shtampuyutsya.
- Skrytyy #2: (Thinking Rules ↔ Avtonomiya) slot mozhno menyat ekshenom/ruchkoy.

Zemnoy abzats:
Kak tumbler s predokhranitelem: mozhno poprobovat “B”, no pri sboe srazu vernut “A”, ne lomaya sistemu.

# c=a+b"""
from __future__ import annotations
import os, functools, traceback
from typing import Callable, Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB_SLOT=os.getenv("AB_SLOT","A").upper()
AB_AUTOROLLBACK=(os.getenv("AB_AUTOROLLBACK","true").lower()=="true")

def _passport(note: str, meta: Dict[str,Any]):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "safety://abslot")
    except Exception:
        pass

def active_slot()->str:
    return os.getenv("AB_SLOT","A").upper() or "A"

def choose(fn_a: Callable[...,Any], fn_b: Callable[...,Any])->Callable[...,Any]:
    """Wrapper: Calls B if B is active; if an exception occurs, it logs and calls A."""
    @functools.wraps(fn_a)
    def wrapper(*args, **kwargs):
        slot=active_slot()
        if slot=="B":
            try:
                return fn_b(*args, **kwargs)
            except Exception as e:
                _passport("abslot_b_fail", {"err": str(e), "trace": traceback.format_exc()[-4000:]})
                if AB_AUTOROLLBACK:
                    # soft switching to A (in the current process)
                    return fn_a(*args, **kwargs)
                raise
        # slot A po umolchaniyu
        return fn_a(*args, **kwargs)
    return wrapper
# c=a+b