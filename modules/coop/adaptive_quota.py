# -*- coding: utf-8 -*-
"""modules/coop/adaptive_quota.py - adaptivnye kvoty po zaderzhke (RTT) vnutri komnaty.

Ideaya:
- Klienty shlyut heartbeat v psevdo-DC (ili pryamo syuda), where nesut svoy rtt_ms (otsenennyy na kliente).
- My derzhim skolzyaschee srednee rtt i rasschityvaem kvotu: quota = clamp(Qmax - k * log1p(rtt_ms), Qmin..Qmax).
- Otdaem kvoty dlya integratsii v game_sync/sync_keyboard.

API:
- config(room, qmin, qmax, k)
- heartbeat(room, client, rtt_ms)
- quotas(room) -> {client: quota}
- status(room)

MOSTY:
- Yavnyy: (Infoteoriya ↔ Spravedlivost) bolee “medlennym” - myagche kvota, “bystrym” - bolshe deystviy.
- Skrytyy #1: (Kibernetika ↔ Stabilnost) snizhaet peregruzku kanala.
- Skrytyy #2: (Inzheneriya ↔ Ekspluatatsiya) simple formula, predskazuemye granitsy.

ZEMNOY ABZATs:
Memory protsessa, skolzyaschee srednee EMA. Nikakikh fonovykh zadach.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_rooms: Dict[str, Dict[str, Any]] = {}  # room -> {qmin,qmax,k, clients: {id:{ema:float,quota:int}}}

def config(room: str, qmin: int, qmax: int, k: float) -> Dict[str, Any]:
    r = _rooms.setdefault(room, {"qmin": qmin, "qmax": qmax, "k": float(k), "clients": {}})
    r.update({"qmin": qmin, "qmax": qmax, "k": float(k)})
    return {"ok": True, **status(room)}

def heartbeat(room: str, client: str, rtt_ms: float) -> Dict[str, Any]:
    r = _rooms.setdefault(room, {"qmin": 2, "qmax": 15, "k": 2.0, "clients": {}})
    c = r["clients"].setdefault(client, {"ema": float(rtt_ms), "quota": r["qmax"]})
    # EMA
    alpha = 0.3
    c["ema"] = (1-alpha)*c["ema"] + alpha*float(rtt_ms)
    # formula kvoty
    import math
    q = int(round(max(r["qmin"], min(r["qmax"], r["qmax"] - r["k"]*math.log1p(max(0.0, c["ema"]))))))
    c["quota"] = q
    return {"ok": True, "client": client, "rtt_ema": round(c["ema"],2), "quota": q}

def quotas(room: str) -> Dict[str, Any]:
    r = _rooms.get(room) or {"clients": {}}
    return {"ok": True, "quotas": {k: v["quota"] for k,v in r["clients"].items()}}

def status(room: str) -> Dict[str, Any]:
    r = _rooms.get(room) or {"qmin":2,"qmax":15,"k":2.0,"clients":{}}
    return {"ok": True, "qmin": r["qmin"], "qmax": r["qmax"], "k": r["k"], "clients": r["clients"]}