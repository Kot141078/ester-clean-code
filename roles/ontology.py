# -*- coding: utf-8 -*-
"""roles/ontology.py - ontologiya roley i ikh semanticheskikh priznakov.

MOSTY:
- (Yavnyy) get_ontology() → dict s opredeleniyami roley (>=20), sinonimami i ozhidaemymi napravleniyami po vektoram.
- (Skrytyy #1) Skhodimost s vektorom: role opisany cherez "hints" po izmereniyam (experience, reaction, calm, ...).
- (Skrytyy #2) Rasshiryaemost: merge_ontology(custom) pozvolyaet dobavlyat/pereopredelyat roli bez migratsiy.

ZEMNOY ABZATs:
Ester derzhit "slovar" roley: kto sklonen k chemu, kak eto raspoznaetsya i chem otlichaetsya "veteran-operator" ot "razvedchik" or "peregovorschik".

# c=a+b"""
from __future__ import annotations

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_BASE: Dict[str, Any] = {
    "version": 1,
    "dims": ["experience","reaction","calm","coop","lead","law","tech","med","edu","craft","comm","creative","stamina","availability"],
    "roles": {
        "operator_veteran": {
            "title": "Operator-veteran",
            "aliases": ["veteran", "senior operator", "starshiy operator"],
            "hints": {"experience":0.9,"calm":0.8,"reaction":0.6}
        },
        "operator_junior": {
            "title": "Operator-novichok",
            "aliases": ["junior operator","novichok","stazher"],
            "hints": {"experience":0.2,"reaction":0.7,"edu":0.5}
        },
        "pilot_fast": {"title":"Pilot-skorostnik","aliases":["bystryy pilot","kurer"],
                       "hints":{"reaction":0.9,"stamina":0.7,"availability":0.8}},
        "scout": {"title":"Razvedchik","aliases":["nablyudatel","razvedchik"],"hints":{"reaction":0.8,"calm":0.7,"creative":0.6}},
        "coordinator": {"title":"Koordinator","aliases":["dispetcher","koordinator"],"hints":{"lead":0.7,"comm":0.9,"coop":0.8}},
        "negotiator": {"title":"Peregovorschik","aliases":["diplomat","mediator"],"hints":{"comm":0.9,"calm":0.8,"lead":0.6}},
        "strategist": {"title":"Strateg","aliases":["analitik","strateg"],"hints":{"creative":0.6,"lead":0.7,"experience":0.8}},
        "tactician": {"title":"Taktik","aliases":["operator taktiki"],"hints":{"reaction":0.7,"coop":0.6,"experience":0.6}},
        "engineer": {"title":"Inzhener","aliases":["tekhnik","engineer"],"hints":{"tech":0.9,"craft":0.8}},
        "mechanic": {"title":"Mekhanik","aliases":["remontnik"],"hints":{"craft":0.9,"tech":0.7,"stamina":0.6}},
        "lawyer": {"title":"Yurist","aliases":["advokat","konsultant po pravu"],"hints":{"law":0.95,"comm":0.7}},
        "doctor": {"title":"Medik","aliases":["vrach","feldsher"],"hints":{"med":0.95,"calm":0.8,"stamina":0.7}},
        "teacher": {"title":"Nastavnik","aliases":["prepodavatel"],"hints":{"edu":0.9,"comm":0.8,"calm":0.7}},
        "student": {"title":"Student","aliases":["uchenik"],"hints":{"edu":0.8,"availability":0.7}},
        "courier": {"title":"Kurer","aliases":["dostavschik"],"hints":{"reaction":0.8,"stamina":0.7,"availability":0.9}},
        "driver": {"title":"Voditel","aliases":["shofer"],"hints":{"reaction":0.7,"stamina":0.7}},
        "guardian": {"title":"Okhrannik","aliases":["bezopasnik"],"hints":{"calm":0.7,"lead":0.5,"reaction":0.6}},
        "rescuer": {"title":"Spasatel","aliases":["reagirovschik"],"hints":{"reaction":0.8,"stamina":0.8,"coop":0.7}},
        "scribe": {"title":"Dokumentalist","aliases":["pisar"],"hints":{"comm":0.8,"law":0.5}},
        "artist": {"title":"Tvorets","aliases":["kreator","dizayner"],"hints":{"creative":0.95,"comm":0.6}},
    }
}

def get_ontology() -> Dict[str, Any]:
    return _BASE

def merge_ontology(custom: Dict[str, Any]) -> Dict[str, Any]:
    out = {**_BASE}
    if not custom: return out
    out["version"] = max(_BASE.get("version",1), custom.get("version",1))
    out["dims"] = list({*(_BASE.get("dims") or []), *(custom.get("dims") or [])})
    roles = {**_BASE.get("roles",{})}
    roles.update(custom.get("roles",{}))
    out["roles"] = roles
    return out