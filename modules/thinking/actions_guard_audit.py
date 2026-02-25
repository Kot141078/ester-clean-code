# -*- coding: utf-8 -*-
"""modules/thinking/actions_guard_audit.py - eksheny “voli” dlya storozha i audita pamyati.

Mosty:
- Yavnyy: (Mysli ↔ Upravlenie) udobnye sokrascheniya dlya statusa/konfiguratsii/audita.
- Skrytyy #1: (RBAC ↔ Ostorozhnost) konfig vypolnyaetsya cherez HTTP-ruchku (uvazhaem roli).
- Skrytyy #2: (Profile) logi pishutsya modulyami-ispolnitelyami.

Zemnoy abzats:
Mozgu ne nado pomnit adresa ruchek - est korotkie komandy.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_status(args: Dict[str,Any]):
        import urllib.request, json
        with urllib.request.urlopen("http://127.0.0.1:8000/thinking/guard/status", timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    register("thinking.guard.status", {}, {"ok":"bool"}, 1, a_status)

    def a_config(args: Dict[str,Any]):
        import urllib.request, json
        body=json.dumps({
            "name": str(args.get("name","")),
            "timeout": args.get("timeout"),
            "wip": args.get("wip"),
            "enabled": args.get("enabled")
        }).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/thinking/guard/config", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    register("thinking.guard.config", {"name":"str"}, {"ok":"bool"}, 1, a_config)

    def a_audit(args: Dict[str,Any]):
        import urllib.request, json
        body=json.dumps({"masks": list(args.get("masks") or [])}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/quality/mm_audit/scan", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    register("quality.mm_audit.scan", {"masks":"list"}, {"ok":"bool"}, 3, a_audit)

_reg()
# c=a+b