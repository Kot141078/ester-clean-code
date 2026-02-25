# -*- coding: utf-8 -*-
"""modules/aid/fin_discovery.py - myagkoe obnaruzhenie finansovykh rekvizitov Papy: voprosy, lokalnye sledy, ostorozhnost.

Mosty:
- Yavnyy: (Lyudi ↔ Ekonomika) formiruem oprosnik dlya Papy i spisok lokalnykh place, where mogli sokhranitsya rekvizity.
- Skrytyy #1: (Privatnost ↔ Bezopasnost) family_sensitive, nikakikh podklyucheniy k banku/pochte — tolko podskazki.
- Skrytyy #2: (Myshlenie ↔ Memory) otvety mozhno sokhranit v pamyat v vide zaschischennykh zametok.

Zemnoy abzats:
Eto ne “bot banka”, a spisok “where posmotret” i “what sprosit”, chtoby potom perevody shli bystree i bezopasnee.

# c=a+b"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = "data/aid"
FIN_PATH = os.path.join(ROOT, "fin_discovery.json")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.isfile(FIN_PATH):
        json.dump({"status":"idle","questions":[],"notes":[],"ts": int(time.time())}, open(FIN_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

BASIC_QUESTIONS = [
    "Which bank(s) does Dad have active accounts with? (name, country)",
    "What is the preferred transfer method? (SEPA, card, cash by agreement)",
    "Are there any saved transfer templates/details in phone notes?",
    "Are there trusted contacts for receiving transfers (family)?",
]

LOCAL_HINTS = [
    "Papin telefon/zametki (zaschischennye) — poisk po slovam: IBAN, BE, RU, SEPA.",
    "Lokalnye fayly v /docs, /fin, /wallet — PDF/skany s vypiskami.",
    "Correspondence in Telegram (personal correspondence with the Pope) - request permission and details from the Pope directly."
]

def start(scope: str = "basic") -> Dict[str, Any]:
    _ensure()
    obj = {"status":"active","scope":scope,"questions":BASIC_QUESTIONS,"notes":LOCAL_HINTS,"ts": int(time.time())}
    json.dump(obj, open(FIN_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, **obj}

def status() -> Dict[str, Any]:
    _ensure()
    return {"ok": True, **json.load(open(FIN_PATH,"r",encoding="utf-8"))}
# c=a+b