# -*- coding: utf-8 -*-
"""modules/thinking/actions_core15.py - eksheny "voli" dlya paketa Core15 (autolink, prioritize, cron).

Mosty:
- Yavnyy: (Mysli ↔ Memory/CRON) edinye korotkie komandy dlya novykh vozmozhnostey.
- Skrytyy #1: (RBAC ↔ Podskazka) v otvetakh vozvraschaem khinty pro roli/ruchki.
- Skrytyy #2: (Zhurnal ↔ Profile) sami podchinennye moduli uzhe kladut profile.

Zemnoy abzats:
This is “goryachie klavishi” dlya novykh funktsiy - chtoby mozgu bylo udobno.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_autolink(args: Dict[str,Any]):
        from modules.mem.retro_linker import tick
        return tick(int(args.get("limit",0)) if args.get("limit") else None)
    register("mem.autolink.tick", {"limit":"int"}, {"ok":"bool"}, 5, a_autolink)

    def a_prior(args: Dict[str,Any]):
        from modules.thinking.affect_reflect import prioritize
        return prioritize(int(args.get("limit",200)), int(args.get("topk",20)))
    register("thinking.reflect.prioritize", {"limit":"int","topk":"int"}, {"ok":"bool"}, 4, a_prior)

    def a_cron(args: Dict[str,Any]):
        from modules.ops.cron import tick
        return tick()
    register("ops.cron.tick", {}, {"ok":"bool"}, 6, a_cron)

_reg()
# c=a+b