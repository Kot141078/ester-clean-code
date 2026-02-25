# -*- coding: utf-8 -*-
"""modules/guard/mm_guard.py - “zhestkaya” tochka vkhoda k pamyati: proksi get_mm() i metriki obkhoda fabriki.

Behavior:
  • Pri importe (esli PROVENANCE_ENFORCE=1) - patchit services.mm_access.get_mm:
      vozvraschaet proksi MemoryManager, avtomaticheski dobavlyayuschiy meta.provenance pri zapisyakh.
  • Esli MM_GUARD_REPORT=1 — vedet schetchiki vyzovov get_mm() i grubuyu evristiku “pryamykh initsializatsiy” (best-effort).

Publichnoe API:
  • counters() -> dict

Mosty:
- Yavnyy: (Memory ↔ Control) odna dver v pamyat cherez fabriku - prosche soblyudat invarianty.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) proksi garantiruet profile na vse novye zapisi.
- Skrytyy #2: (Inzheneriya ↔ Podderzhka) metriki pokazyvayut “who idet v obkhod”, ne lomaya legasi.

Zemnoy abzats:
Eto kak turniket pered arkhivom: vse prokhodyat cherez odin prokhod - vsem stavyat shtamp i schitayut posescheniya.

# c=a+b"""
from __future__ import annotations

import importlib
import os
import threading
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PROVENANCE_ENFORCE = bool(int(os.getenv("PROVENANCE_ENFORCE", "1")))
_REPORT = bool(int(os.getenv("MM_GUARD_REPORT", "1")))

_lock = threading.Lock()
_cnt = {"get_mm_calls_total": 0, "direct_inits_total": 0, "patched": 0}

def _try_patch_get_mm():
    try:
        mm_access = importlib.import_module("services.mm_access")
        orig = getattr(mm_access, "get_mm", None)
        if not callable(orig):
            return
        from modules.memory.provenance_unified import wrap_mm  # type: ignore

        def _patched(*args, **kwargs):
            with _lock:
                _cnt["get_mm_calls_total"] += 1
            mm = orig(*args, **kwargs)
            return wrap_mm(mm)

        setattr(mm_access, "get_mm", _patched)
        with _lock:
            _cnt["patched"] = 1
    except Exception:
        pass

def _install_direct_init_probe():
    """Best-effort: pytaemsya obnaruzhit pryamye new Storage/VectorStore i uvelichit schetchik.
    Realizatsiya myagkaya (bez blokirovok): patchim kandidatov, esli oni est."""
    try:
        # Primer: modules.memory.storage.Storage / modules.memory.vector.VectorStore (imena uslovny)
        for mod_name, cls_name in [("modules.memory.storage", "Storage"),
                                   ("modules.memory.vector", "VectorStore"),
                                   ("modules.memory.manager", "MemoryManager")]:
            try:
                m = importlib.import_module(mod_name)
                cls = getattr(m, cls_name, None)
                if cls is None:
                    continue
                orig_new = getattr(cls, "__init__", None)
                if not callable(orig_new):
                    continue

                def _wrap_init(orig):
                    def inner(self, *a, **kw):
                        with _lock:
                            _cnt["direct_inits_total"] += 1
                        return orig(self, *a, **kw)
                    return inner

                setattr(cls, "__init__", _wrap_init(orig_new))
            except Exception:
                continue
    except Exception:
        pass

def counters() -> Dict[str, Any]:
    with _lock:
        return dict(_cnt)

# Initsializatsiya pri importe
if _PROVENANCE_ENFORCE:
    _try_patch_get_mm()
if _REPORT:
    _install_direct_init_probe()
