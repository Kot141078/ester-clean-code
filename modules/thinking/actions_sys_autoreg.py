# -*- coding: utf-8 -*-
"""modules/thinking/actions_sys_autoreg.py - eksheny “voli” dlya avtosborki i doveriya k kodu.

Mosty:
- Yavnyy: (Mysli ↔ Sborka) zapuskaem autoreg pryamo iz planov voli.
- Skrytyy #1: (Bezopasnost ↔ RBAC) operatsii kod-doveriya ogranicheny.
- Skrytyy #2: (Memory ↔ Profile) otrazhaetsya zhurnal vremeni.

Zemnoy abzats:
Brain says: “check new moduli”, - i sborschik prokhodit po sistemnoy polke.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def a_autoreg(args: Dict[str,Any]):
        # HTTP call local handle to respect RVACH/policies
        import json, urllib.request
        body=json.dumps({"scan": list(args.get("scan") or [])}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/sys/autoreg/tick", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("sys.autoreg.tick", {"scan":"list"}, {"ok":"bool"}, 4, a_autoreg)

    def a_wl(args: Dict[str,Any]):
        import json, urllib.request
        body=json.dumps({"path": str(args.get("path","")), "sha256": args.get("sha256")}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000/sys/codetrust/whitelist", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    register("sys.codetrust.whitelist", {"path":"str","sha256":"str"}, {"ok":"bool"}, 2, a_wl)

_reg()
# c=a+b