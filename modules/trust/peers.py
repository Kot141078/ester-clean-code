# -*- coding: utf-8 -*-
"""modules/trust/peers.py - reestr doverennykh uzlov (pirov) s ikh publichnymi klyuchami.

Mosty:
- Yavnyy: (Set ↔ Doverie) kto imeet pravo priglashat/podpisyvat deystvie.
- Skrytyy #1: (Infoteoriya ↔ Audit) khranenie s otpechatkami i vremenem dobavleniya.
- Skrytyy #2: (Kibernetika ↔ Kontrol) ispolzuetsya proverkoy priglasheniy i SpreadGuard.

Zemnoy abzats:
Spisok “svoikh”: id, imya, algoritm i publichnyy klyuch - bez etogo nelzya bezopasno “prosit” i “razreshat”.

# c=a+b"""
from __future__ import annotations
import json, os, hashlib, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

TRUST_STORE_PATH = os.getenv("TRUST_STORE_PATH","data/trust/peers.json")

def _ensure():
    os.makedirs(os.path.dirname(TRUST_STORE_PATH), exist_ok=True)
    if not os.path.isfile(TRUST_STORE_PATH):
        json.dump({"peers":[]}, open(TRUST_STORE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def list_peers() -> Dict[str, Any]:
    _ensure()
    return json.load(open(TRUST_STORE_PATH,"r",encoding="utf-8"))

def add_peer(pid: str, name: str, alg: str, pubkey_b64: str) -> Dict[str, Any]:
    _ensure()
    st = json.load(open(TRUST_STORE_PATH,"r",encoding="utf-8"))
    fp = hashlib.sha256((alg + ":" + pubkey_b64).encode("utf-8")).hexdigest()
    for p in st["peers"]:
        if p.get("id")==pid or p.get("fingerprint")==fp:
            return {"ok": True, "updated": False, "id": pid, "fingerprint": fp}
    st["peers"].append({"id": pid, "name": name, "alg": alg, "pubkey": pubkey_b64, "fingerprint": fp, "ts": int(time.time())})
    json.dump(st, open(TRUST_STORE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "updated": True, "id": pid, "fingerprint": fp}

def find_by_id(pid: str) -> Dict[str, Any] | None:
    _ensure()
    st = json.load(open(TRUST_STORE_PATH,"r",encoding="utf-8"))
    for p in st["peers"]:
        if p.get("id")==pid:
            return p
    return None
# c=a+b