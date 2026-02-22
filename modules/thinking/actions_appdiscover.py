# -*- coding: utf-8 -*-
"""
modules/thinking/actions_appdiscover.py — eksheny dlya «voli» vokrug AppDiscover+.

Mosty:
- Yavnyy: (Mysli ↔ Prilozhenie) volya mozhet sama initsiirovat scan/register.
- Skrytyy #1: (Ekonomika ↔ CostFence) dvizheniya legkie, byudzhet minimalnyy.
- Skrytyy #2: (Resilience ↔ Audit) registriruem sha/ts v reestre — legko otkatit cherez Forge.

Zemnoy abzats:
Mozg prosit: «posmotri, chto novogo», «podklyuchi vot eto» — i ruki delayut.

# c=a+b
"""
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
        # registrirovat v deystviyakh bez Flask nelzya — ruchka HTTP zanimaetsya vyzovom register(app)
        # zdes vozvraschaem podskazku vyzyvat HTTP-ruchku
        mods=list(args.get("modules") or [])
        return {"ok": True, "hint":"use /app/discover/register HTTP", "modules": mods}
    register("app.discover.register", {"modules":"list"}, {"ok":"bool"}, 1, a_register)

_reg()
# c=a+b