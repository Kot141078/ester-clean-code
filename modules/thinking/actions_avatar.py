# -*- coding: utf-8 -*-
"""
modules/thinking/actions_avatar.py — eksheny «voli» dlya orkestratora i veduschego.

Mosty:
- Yavnyy: (Mysli ↔ Orkestrator) vybrat provaydery, sobrat rolik.
- Skrytyy #1: (Avtonomiya ↔ Puls) mozhno vyzyvat na raspisanii/sobytiyakh.
- Skrytyy #2: (Ekonomika) v buduschem dopolnim otsenkoy CostFence pryamo v selektore.

Zemnoy abzats:
Komanda «soberi veduschego iz vot etogo teksta» — i konveyer sdelaet vse sam.

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

    def a_models(args: Dict[str,Any]):
        from modules.studio.models.registry import list_providers
        return {"ok": True, "providers": list_providers()}
    register("studio.models.refresh", {}, {"ok":"bool"}, 2, a_models)

    def a_make(args: Dict[str,Any]):
        from modules.studio.avatar import make
        return make(str(args.get("title","Host")), list(args.get("script") or []), dict(args.get("avatar") or {}), dict(args.get("tts") or {}), bool(args.get("consent", False)))
    register("studio.avatar.make", {"title":"str","script":"list"}, {"ok":"bool"}, 18, a_make)

_reg()
# c=a+b