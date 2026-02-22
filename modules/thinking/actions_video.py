# -*- coding: utf-8 -*-
"""
modules/thinking/actions_video.py — ekshen «voli» dlya komponovki video.

Mosty:
- Yavnyy: (Mysli ↔ Kompozer) daet korotkuyu komandu «sobrat rolik».
- Skrytyy #1: (Strategiya ↔ Publikatsiya) rezultat srazu dostupen dlya SocialDeploy.
- Skrytyy #2: (Avtonomiya ↔ Sobytiya) mozhno vshit v pipeline: «est drama/avatar → sdelay short».

Zemnoy abzats:
Mozg govorit «soberi short po shablonu» — i poluchaetsya gotovyy mp4, godnyy dlya TikTok/YouTube.

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
    def a_compose(args: Dict[str,Any]):
        import json, urllib.request
        body=json.dumps(args or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/studio/video/compose", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=216000) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("studio.video.compose", {"title":"str","aspect":"str"}, {"ok":"bool"}, 10, a_compose)

_reg()
# c=a+b



