# -*- coding: utf-8 -*-
"""modules/thinking/actions_appdiscover.py - eksheny dlya "voli" vokrug AppDiscover+.

Mosty:
- Yavnyy: (Mysli ↔ Prilozhenie) volya mozhet sama initsiirovat scan/register.
- Skrytyy #1: (Ekonomika ↔ CostFence) dvizheniya legkie, byudzhet minimalnyy.
- Skrytyy #2: (Resilience ↔ Audit) registriruem sha/ts v reestre — legko otkatit cherez Forge.

Zemnoy abzats:
Brain prosit: “look, what novogo”, “podklyuchi vot eto” - i ruki delayut.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_scan(args: Dict[str,Any]):
        from modules.app.discover import scan
        return scan()
    register("app.discover.scan", {}, {"ok":"bool","items":"list"}, 3, a_scan)

    def a_status(args: Dict[str,Any]):
        from modules.app.discover import status
        return status()
    register("app.discover.status", {}, {"ok":"bool"}, 1, a_status)

    def a_register(args: Dict[str,Any]):
        from modules.app.discover import register_modules
        # It is impossible to register in actions without Flask - the NTTP handle is responsible for calling the register(app)
        # here we return a hint to call the HTTP handle
        mods=list(args.get("modules") or [])
        return {"ok": True, "hint":"use /app/discover/register HTTP", "modules": mods}
    register("app.discover.register", {"modules":"list"}, {"ok":"bool"}, 1, a_register)

_reg()
# c=a+b