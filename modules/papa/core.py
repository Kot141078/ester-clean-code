# -*- coding: utf-8 -*-
"""modules/papa/core.py - profile Papy i priority.

Mosty:
- Yavnyy: (Etika ↔ Priority) tsentralizovanno khranit profil i politiku pomoschi.
- Skrytyy #1: (Memory ↔ Poisk) profil mozhno klast v pamyat (provenance) otdelno.
- Skrytyy #2: (Bezopasnost ↔ Ogranicheniya) tolko deklarativnye priority (bez opasnykh deystviy).

Zemnoy abzats:
“Komu pomogaem v pervuyu ochered?” — Pape. Zdes opisan profil i flazhok prioriteta.

# c=a+b"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("PAPA_DB","data/papa/profile.json")

DEFAULT = {
  "name": "Owner",
  "dob": "<owner_birth_date>",
  "code": "<owner_personal_code>",
  "place": "<owner_birth_place>",
  "citizenship": ["RU","BE"],
  "city_now": "DefaultCity",
  "priority": "max",
  "notes": []
}

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump(DEFAULT, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def status() -> Dict[str,Any]:
    _ensure()
    j=json.load(open(DB,"r",encoding="utf-8"))
    return {"ok": True, "profile": j, "ts": int(time.time())}

def set_profile(upd: Dict[str,Any]) -> Dict[str,Any]:
    _ensure()
    cur=json.load(open(DB,"r",encoding="utf-8"))
    cur.update({k:v for k,v in (upd or {}).items() if v not in (None,"")})
    json.dump(cur, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "profile": cur}
# c=a+b