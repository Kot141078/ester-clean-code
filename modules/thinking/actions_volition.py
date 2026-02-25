# -*- coding: utf-8 -*-
"""modules/thinking/actions_volition.py - tonkaya integratsiya "voli" v action_registry.

Mosty:
- Yavnyy: (Mysli ↔ Volya) daem mozgu kirpichiki upravlyat tikom/konfigom bez HTTP.
- Skrytyy #1: (Ekonomika ↔ Byudzhet) deystviya legkie i pochti besplatnye.
- Skrytyy #2: (Audit ↔ Memory) tik logiruet itogi i shlet profile.

Zemnoy abzats:
Esli samoy Ester “stuknulo v golovu” - ona mozhet dernut puls napryamuyu, ne zovya panel.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_tick(args: Dict[str,Any]):
        from modules.volition.pulse import tick
        return tick(pill=str(args.get("pill","")))
    register("volition.pulse.tick", {"pill":"str"}, {"ok":"bool"}, 10, a_tick)

    def a_status(args: Dict[str,Any]):
        from modules.volition.pulse import status
        return status()
    register("volition.pulse.status", {}, {"ok":"bool"}, 1, a_status)

_reg()
# c=a+b