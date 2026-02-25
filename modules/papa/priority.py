# -*- coding: utf-8 -*-
"""modules/papa/priority.py - profil Papy i vesa prioritetov (care/funds/safety), bez setey i platezhey.

Mosty:
- Yavnyy: (Semya ↔ Politiki) yavnye vesa dlya planirovschika.
- Skrytyy #1: (Infoteoriya ↔ Memory) profil khranitsya lokalno i mozhet sinkhronizirovatsya tvoimi sredstvami.
- Skrytyy #2: (Kibernetika ↔ Ostorozhnost) tolko myagkie signaly, nikakoy “magii” perevoda sredstv.

Zemnoy abzats:
Dokument “what dlya Papy vazhno” - what Ester planirovala s oglyadkoy.

# c=a+b"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PATH = os.getenv("PAPA_PROFILE","data/papa/profile.json")

DEFAULT = {
  "owner": {
    "name": "Owner",
    "dob": "<owner_birth_date>",
    "id_hint": "<owner_personal_code>",
    "cities": ["<owner_birth_place>","DefaultCity"],
    "citizenship": ["RU","BE"]
  },
  "weights": {"care": 1.0, "funds": 1.0, "safety": 1.0},
  "ts": 0
}

def _ensure():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    if not os.path.isfile(PATH):
        obj=dict(DEFAULT); obj["ts"]=int(time.time())
        json.dump(obj, open(PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def get() -> Dict[str, Any]:
    _ensure()
    return json.load(open(PATH,"r",encoding="utf-8"))

def set_weights(weights: Dict[str, float]) -> Dict[str, Any]:
    _ensure()
    obj=json.load(open(PATH,"r",encoding="utf-8"))
    obj["weights"].update({k: float(v) for k,v in (weights or {}).items()})
    obj["ts"]=int(time.time())
    json.dump(obj, open(PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "profile": obj}
# c=a+b