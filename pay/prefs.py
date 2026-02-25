# -*- coding: utf-8 -*-
"""modules/pay/prefs.py - platezhnye predpochteniya Papy (instruktsii dlya schetov/pisem).

Mosty:
- Yavnyy: (Finance/Outreach ↔ Papa) tsentralizovannye rekvizity v odnom meste.
- Skrytyy #1: (Invoice ↔ Integratsiya) te zhe stroki mozhno podstavlyat v meta scheta.
- Skrytyy #2: (Passport ↔ Prozrachnost) izmeneniya fiksiruyutsya.

Zemnoy abzats:
Odin reference rekvizitov: chtoby kazhdyy raz ne vspominat IBAN/PayPal - podstavilos avtomaticheski i bez oshibok.

# c=a+b"""
from __future__ import annotations
import os
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

FIELDS=("DAD_NAME","DAD_EMAIL","DAD_IBAN","DAD_BIC","DAD_PAYPAL","DAD_USDT")

def get()->Dict[str,Any]:
    return {"ok": True, "prefs": {k: os.getenv(k,"") for k in FIELDS}}

def set_(d: Dict[str,Any])->Dict[str,Any]:
    for k in FIELDS:
        if k in d: os.environ[k]=str(d[k])
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("pay_prefs_set", {"fields": [k for k in FIELDS if k in d]}, "finance://prefs")
    except Exception:
        pass
    return get()
# c=a+b