# -*- coding: utf-8 -*-
"""
modules/thinking/actions_drama.py — eksheny «voli» dlya TTS i audiodramy.

Mosty:
- Yavnyy: (Mysli ↔ Studiya) korotkie komandy dlya sinteza i sborki roley.
- Skrytyy #1: (Plan ↔ Avtomatizatsiya) mozhno stavit na sobytiynyy payplayn (napr., «est glava — ozvuch»).
- Skrytyy #2: (Monetizatsiya ↔ Sotsdeploy) rezultat legko otpravit v SocialDeploy.

Zemnoy abzats:
Mozg daet prikaz «ozvuchit» ili «postavit pesu» — i konveyer delaet ostalnoe.

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

    def a_tts(args: Dict[str,Any]):
        import json, urllib.request
        body=json.dumps({"text": str(args.get("text","")), "voice": str(args.get("voice",""))}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/studio/tts/say", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("studio.tts.say", {"text":"str","voice":"str"}, {"ok":"bool"}, 1, a_tts)

    def a_drama(args: Dict[str,Any]):
        import json, urllib.request
        body=json.dumps({
            "title": str(args.get("title","Untitled")),
            "script": list(args.get("script") or []),
            "voices": dict(args.get("voices") or {}),
            "gap_ms": int(args.get("gap_ms",250))
        }).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/studio/drama/make", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=21600) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("studio.drama.make", {"title":"str","script":"list"}, {"ok":"bool"}, 12, a_drama)

_reg()
# c=a+b


