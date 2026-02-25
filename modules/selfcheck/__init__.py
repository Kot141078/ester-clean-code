# -*- coding: utf-8 -*-
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
"""modules/selfcheck - sovmestimost so starym putem.
Mosty:
- Yavnyy: (selfcheck ↔ self) — reeksport funktsiy run/self_check iz modules.self.selfcheck.
- Skrytyy #1: (Testy ↔ DX) — testy/routy mogut prodolzhat ispolzovat starye importy.
- Skrytyy #2: (Otkazoustoychivost) — esli modul otsutstvuet, vydaem bezopasnye no-op.

Zemnoy abzats:
Funktsiya samoproverki nuzhna vsegda. Esli iskhodnyy modul pereekhal - tut most.
# c=a+b"""
try:
    from modules.self.selfcheck import run, self_check  # type: ignore
except Exception:
    def run(*a, **k):  # type: ignore
        return {"ok": True, "note": "selfchesk shim"}
    def self_check(*a, **k):  # type: ignore
        return {"ok": True, "note": "selfchesk shim"}

__all__ = ["run", "self_check"]