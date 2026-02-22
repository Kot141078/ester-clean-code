# -*- coding: utf-8 -*-
"""
modules/thinking/actions_selfmap_invoice.py — eksheny «voli» dlya Samokarty/Dashborda/Schetov.

Mosty:
- Yavnyy: (Mysli ↔ Upravlenie/Finansy) bystrye komandy na snimok, HTML-dashbord i schet.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse fiksiruetsya.
- Skrytyy #2: (Garage/Market ↔ Svyazka) mozhno vstraivat v otkliki frilansa.

Zemnoy abzats:
S etimi knopkami Ester mozhet posmotret na sebya so storony i tut zhe oformit rabotu dokumentalno.

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=20):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=60):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("self.map", {}, {"ok":"bool"}, 1, lambda a: _get("/self/map"))
    register("app.dashboard.html", {}, {"ok":"bool"}, 1, lambda a: _get("/app/dashboard"))
    register("finance.invoice.create", {"data":"object"}, {"ok":"bool"}, 2, lambda a: _post("/finance/invoice/create", dict(a.get("data") or {})))
    register("finance.invoice.get", {"id":"str","format":"str"}, {"ok":"bool"}, 1, lambda a: _get(f"/finance/invoice/get?id={a.get('id','')}&format={a.get('format','md')}"))
_reg()
# c=a+b