# -*- coding: utf-8 -*-
"""modules/runtime/ab_unified.py - edinaya tochka vkhoda k dvum raznym “A/B” zadacham.

Mosty:
- Yavnyy: (abslots ↔ ab_slots) — svodim dva raznykh smyslovykh sloya pod odin fasad.
- Skrytyy #1: (Routy/CLI ↔ Runtime) - tem, komu nuzhen “odin import”, ne nuzhno pomnit dva imeni.
- Skrytyy #2: (Samovosstanovlenie ↔ Bezopasnaya samo-redaktura) — fasad ne lomaet starye importy.

Zemnoy abzats:
V code est dva "A/B": runtime-sloty sborki/bandlov (`abslots`) i A/B komponentov s TTL (`ab_slots`).
This modul nichego ne pereimenovyvaet i ne lomaet, on prosto daet udobnye khelpery i neymspeysy.
# c=a+b"""
from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Namespaces: this makes it easier to distinguish between levels
try:
    from . import abslots as runtime  # control of the entire active A/B slot
except Exception as e:  # pragma: no cover
    runtime = None  # type: ignore

try:
    from . import ab_slots as components  # A/B konkretnykh komponentov s TTL/health/commit/rollback
except Exception as e:  # pragma: no cover
    components = None  # type: ignore

# ---- Convenient shortcuts: Rintite (release/bundle slots) -----------------------------------------

def runtime_status() -> Dict[str, Any]:
    if runtime is None:
        return {"ok": False, "error": "runtime_module_unavailable"}
    try:
        return runtime.status()  # type: ignore[attr-defined]
    except Exception as e:
        return {"ok": False, "error": str(e)}

def runtime_switch(slot: str, dry_run: bool = False) -> Dict[str, Any]:
    if runtime is None:
        return {"ok": False, "error": "runtime_module_unavailable"}
    try:
        return runtime.switch(slot, dry_run=dry_run)  # type: ignore[attr-defined]
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ---- Convenient shortcuts: Components (A/B by components) ----------------------------------------

def components_status(component: str) -> Dict[str, Any]:
    if components is None:
        return {"ok": False, "error": "components_module_unavailable"}
    try:
        return components.status(component)  # type: ignore[attr-defined]
    except Exception as e:
        return {"ok": False, "error": str(e)}

def components_set(component: str, slot: str, ttl_sec: int | None = None) -> Dict[str, Any]:
    if components is None:
        return {"ok": False, "error": "components_module_unavailable"}
    try:
        return components.set_slot(component, slot, ttl_sec=ttl_sec)  # type: ignore[attr-defined]
    except Exception as e:
        return {"ok": False, "error": str(e)}

def components_report(component: str, ok: bool) -> Dict[str, Any]:
    if components is None:
        return {"ok": False, "error": "components_module_unavailable"}
    try:
        return components.report(component, ok)  # type: ignore[attr-defined]
    except Exception as e:
        return {"ok": False, "error": str(e)}

# c=a+b
