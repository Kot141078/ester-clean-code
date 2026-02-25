# -*- coding: utf-8 -*-
"""modules/thinking/actions_opps_outreach_pay.py - eksheny "voli": Opps/Outreach/Pay.

Mosty:
- Yavnyy: (Mysli ↔ CRM/Outreach/Pay) edinye knopki dlya poiska raboty, generatsii predlozheniy i rekvizitov.
- Skrytyy #1: (Profile ↔ Prozrachnost) vse shagi fiksiruyutsya.
- Skrytyy #2: (Garage/Portfolio ↔ Sinergiya) predlozheniya ssylayutsya na vitrinu.

Zemnoy abzats:
Eti komandy prevraschayut “zametil shans” → “otkliknulsya” → “poluchil oplatu” v odin potok bez ruchnoy rutiny.

# c=a+b"""
from __future__ import annotations
import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    def _get(path: str, timeout: int=30):
        with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))
    def _post(path: str, payload: dict, timeout: int=120):
        data=json.dumps(payload or {}).encode("utf-8")
        req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json as _j; return _j.loads(r.read().decode("utf-8"))

    register("opps.list", {"status":"str"}, {"ok":"bool"}, 1, lambda a: _get("/opps/list"+(f"?status={a.get('status')}" if a.get("status") else "")))
    register("opps.add", {"data":"object"}, {"ok":"bool"}, 2, lambda a: _post("/opps/add", dict(a.get("data") or {})))
    register("opps.import", {"url":"str","skills":"list"}, {"ok":"bool"}, 2, lambda a: _post("/opps/import", {"url": a.get("url",""), "skills": list(a.get("skills") or [])}))
    register("opps.status", {"id":"str","status":"str","notes":"str"}, {"ok":"bool"}, 1, lambda a: _post("/opps/status", {"id": a.get("id",""), "status": a.get("status",""), "notes": a.get("notes","")}))

    register("outreach.proposal.generate", {"opp_id":"str","extras":"object"}, {"ok":"bool"}, 2, lambda a: _post("/outreach/proposal/generate", {"opp_id": a.get("opp_id",""), "extras": dict(a.get("extras") or {})}))
    register("outreach.proposal.get", {"id":"str","format":"str"}, {"ok":"bool"}, 1, lambda a: _get(f"/outreach/proposal/get?id={a.get('id','')}&format={a.get('format','md')}"))

    register("pay.prefs.get", {}, {"ok":"bool"}, 1, lambda a: _get("/pay/prefs"))
    register("pay.prefs.set", {"prefs":"object"}, {"ok":"bool"}, 1, lambda a: _post("/pay/prefs", dict(a.get("prefs") or {})))
_reg()
# c=a+b