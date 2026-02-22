# -*- coding: utf-8 -*-
"""
modules/coop/game_binding.py — privyazka multi-lidera k game_sync.

Naznachenie:
- One-shot bind(room, leader, tick_rate?, quota?) — nastraivaet game_sync na ukazannyy room,
  fiksiruet lidera v multi_leader i vklyuchaet flag «sledovat za ML».
- follow_ml(flag) — esli vklyucheno, lyubye izmeneniya lidera v /multi_leader perenosyatsya v game_sync
  (cherez yavnyy vyzov refresh() iz UI/skripta; fonovykh demonov net).
- refresh(room) — sinkhroniziruet tekuschego lidera i room v game_sync (bez start/stop).

Kontrakty:
- NE menyaem signatury game_sync, multi_leader; rabotaem ikh publichnymi REST-ruchkami.

MOSTY:
- Yavnyy: (Orkestratsiya ↔ Takt) lider → taktirovanie i pometki v igre.
- Skrytyy #1: (Infoteoriya ↔ Prozrachnost) ruchnoy refresh vmesto fonovoy magii.
- Skrytyy #2: (Kibernetika ↔ Kontrol) liderstvo — yavnyy akt, sinkhronizatsiya — po knopke.

ZEMNOY ABZATs:
Vsya logika — HTTP-vyzovy k uzhe suschestvuyuschim ruchkam, sostoyanie — v pamyati.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"follow_ml": True, "room": None}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def bind(room: str, leader: str, tick_rate: int = 20, quota: int = 5) -> Dict[str, Any]:
    _state["room"] = room
    # sozdaem/fiksiruem lidera v ML
    _post("/multi_leader/create", {"room": room, "leader": leader})
    # nastraivaem game_sync
    cfg = _post("/game/config", {"tick_rate": int(tick_rate), "peers": [], "quota": int(quota), "room": room})
    return {"ok": True, "room": room, "leader": leader, "game": cfg}

def follow_ml(flag: bool) -> Dict[str, Any]:
    _state["follow_ml"] = bool(flag)
    return {"ok": True, "follow_ml": _state["follow_ml"]}

def refresh(room: str | None = None) -> Dict[str, Any]:
    rm = room or _state.get("room")
    if not rm:
        return {"ok": False, "error": "no_room"}
    if not _state.get("follow_ml", True):
        return {"ok": True, "skipped": True, "follow_ml": False}
    st = _get(f"/multi_leader/status?room={rm}")
    leader = st.get("leader")
    # Prostavlyaem room esche raz, chtoby metka ne poteryalas
    cfg = _post("/game/config", {"tick_rate": 20, "peers": [], "quota": 5, "room": rm})
    return {"ok": True, "room": rm, "leader": leader, "game": cfg}

def status() -> Dict[str, Any]:
    return {"ok": True, **_state}