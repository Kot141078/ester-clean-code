# -*- coding: utf-8 -*-
"""
modules/audience_infer.py — Passivnye evristiki tipa poluchatelya (bez oprosov).

MOSTY:
- (Yavnyy) infer_audience(meta, text) → 'bank'|'lawyer'|'gov'|'business'|... + confidence.
- (Skrytyy #1) Uchityvaet imya/username/domeny i klyuchevye terminy v tekste.
- (Skrytyy #2) Ne trebuet PII: mozhno peredavat obezlichennyy profil/metki.

ZEMNOY ABZATs:
Pomogaet Ester avtomaticheski vybirat stil pisma/soobscheniya i kanal, esli polzovatel ne ukazal yavno.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BANK_KEYS = ["bank", "bank", "iban", "swift", "bic", "schet", "vypiska", "perevod", "kredit", "zaym"]
LAW_KEYS  = ["advokat", "law", "yurist", "isk", "sud", "dogovor", "pretenz", "arbitrazh"]
GOV_KEYS  = ["minister", "nalog", "munitsip", "gosuslug", "gov", "gos", "viza", "migrats"]
MED_KEYS  = ["vrach", "klinik", "med", "appointment", "diagnoz", "naznachenie"]
EDU_KEYS  = ["shkol", "univer", "uchitel", "dz", "domashka", "kontrolnaya", "kurs"]
BIZ_KEYS  = ["invoys", "schet", "kontragent", "dogovor", "proekt", "menedzher", "zakaz"]

def _score(text: str, keys: list[str]) -> int:
    t = (text or "").lower()
    return sum(1 for k in keys if k in t)

def infer_audience(meta: Dict[str, Any] | None, text: str) -> Tuple[str, float]:
    meta = meta or {}
    src = " ".join([str(meta.get(k) or "") for k in ("name","username","domain","org","bio")]).lower()
    t = (text or "").lower()
    bank = _score(src + " " + t, BANK_KEYS)
    law  = _score(src + " " + t, LAW_KEYS)
    gov  = _score(src + " " + t, GOV_KEYS)
    med  = _score(src + " " + t, MED_KEYS)
    edu  = _score(src + " " + t, EDU_KEYS)
    biz  = _score(src + " " + t, BIZ_KEYS)
    best = max([("bank",bank),("lawyer",law),("gov",gov),("medic",med),("teacher",edu),("business",biz)], key=lambda x:x[1])
    if best[1] == 0:
        return "neutral", 0.0
    conf = min(1.0, 0.2 * best[1])
    return best[0], conf