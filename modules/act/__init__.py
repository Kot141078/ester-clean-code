
# -*- coding: utf-8 -*-
"""
modules.act — sovmestimost dlya runner.run_plan (fiks rekursii).
Mosty:
- Yavnyy: pri importe paketa obespechivaem nalichie funktsii run_plan v modules.act.runner.
- Skrytyy #1: (DX ↔ Nadezhnost) — tselevaya funktsiya vybiraetsya odin raz i keshiruetsya (nikakoy rekursii).
- Skrytyy #2: (Orkestratsiya ↔ Ispolnenie) — podderzhka raznykh imen tselevoy funktsii.

Zemnoy abzats:
Ranshe folbek iskal 'run_plan' sredi kandidatov i mog vyzvat sam sebya → rekursiya.
Teper my isklyuchaem 'run_plan' i fiksiruem ssylku na realnuyu funktsiyu odin raz.
# c=a+b
"""
from __future__ import annotations
from importlib import import_module
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _install_run_plan_fallback():
    try:
        runner = import_module("modules.act.runner")
    except Exception:
        return False
    if hasattr(runner, "run_plan"):
        return True

    # Vybiraem tselevuyu funktsiyu ODIN RAZ, isklyuchaya run_plan (chtoby ne vyzvat sebya)
    target = None
    for name in ("run", "execute_plan", "execute", "main"):
        fn = getattr(runner, name, None)
        if callable(fn):
            target = fn
            break

    def _compat_run_plan(plan, *args, **kwargs):
        if callable(target):
            try:
                return target(plan, *args, **kwargs)
            except TypeError:
                try:
                    return target(plan)
                except Exception:
                    return {
                        "ok": False,
                        "reason_code": "run_plan_target_signature_mismatch",
                        "how_to_enable": "Expose runner.run/execute_plan/execute/main with a compatible signature.",
                    }
        # no target — yavnyy capability-denial
        title = getattr(plan, "name", None) if plan is not None else None
        return {
            "ok": False,
            "reason_code": "run_plan_target_missing",
            "plan": title,
            "how_to_enable": "Implement one of modules.act.runner: run, execute_plan, execute, or main.",
        }

    try:
        setattr(runner, "run_plan", _compat_run_plan)
        return True
    except Exception:
        return False

_install_run_plan_fallback()
