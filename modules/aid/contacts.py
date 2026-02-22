# -*- coding: utf-8 -*-
"""
modules/aid/contacts.py — reestr kontaktov i predpochteniy dlya ekstrennoy pomoschi Pape.

Mosty:
- Yavnyy: (Lyudi ↔ Operatsii) tsentralizovannyy spisok «kogo i kak» uvedomlyat (Papa, semya, sosedi, vrach, sluzhby).
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) proverka kontaktov (verify code), profile zapisi s sha i ts.
- Skrytyy #2: (Politika ↔ Prioritet) pometki family_sensitive + bias k Pape dlya planirovschikov.

Zemnoy abzats:
Prakticheski — eto «kartochka telefona» s prioritetami i pometkami «proveren», chtoby v kriticheskiy moment ne gadat.

# c=a+b
"""
from __future__ import annotations
import hashlib, json, os, time, uuid
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = "data/aid"
CONTACTS = os.path.join(ROOT, "contacts.json")
PREFS = os.path.join(ROOT, "prefs.json")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.isfile(CONTACTS):
        json.dump({"contacts":[]}, open(CONTACTS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    if not os.path.isfile(PREFS):
        json.dump({"sos_hotword":"Ester, pomosch","fallback_country":"BE","notes":""}, open(PREFS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _sha(obj: Any) -> str:
    import json as _j, hashlib as _h
    return _h.sha256(_j.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def get_all() -> Dict[str, Any]:
    _ensure()
    return {
        "ok": True,
        "contacts": json.load(open(CONTACTS,"r",encoding="utf-8")).get("contacts",[]),
        "prefs": json.load(open(PREFS,"r",encoding="utf-8")),
    }

def add(kind: str, name: str, channel: str, value: str, priority: int = 5, note: str = "") -> Dict[str, Any]:
    _ensure()
    st = json.load(open(CONTACTS,"r",encoding="utf-8"))
    cid = str(uuid.uuid4())
    entry = {
        "id": cid, "kind": kind, "name": name, "channel": channel, "value": value,
        "priority": int(priority), "note": note, "verified": False, "ts": int(time.time()),
        "meta": {"family_sensitive": True}
    }
    entry["sha256"] = _sha(entry)
    st["contacts"].append(entry)
    json.dump(st, open(CONTACTS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "id": cid, "sha256": entry["sha256"]}

def verify(cid: str, code: str) -> Dict[str, Any]:
    """
    «Verifikatsiya» po kodu — ruchnaya otmetka (operator/Papa vvodit kod, kotoryy otpravlyalsya izvne).
    V nashem drop-in net realnoy rassylki, no zhurnalim fakt podtverzhdeniya.
    """
    _ensure()
    st = json.load(open(CONTACTS,"r",encoding="utf-8"))
    for c in st["contacts"]:
        if c["id"] == cid:
            c["verified"] = True
            c["verified_ts"] = int(time.time())
            c["verify_note"] = f"manual:{code}"
            json.dump(st, open(CONTACTS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            return {"ok": True}
    return {"ok": False, "error":"not found"}

def set_prefs(**kwargs) -> Dict[str, Any]:
    _ensure()
    pr = json.load(open(PREFS,"r",encoding="utf-8"))
    pr.update({k:v for k,v in kwargs.items() if v is not None})
    json.dump(pr, open(PREFS,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **pr}
# c=a+b