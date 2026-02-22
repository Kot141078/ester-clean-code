# -*- coding: utf-8 -*-
"""
modules/ethics/guard.py — otsenka namereniy (allow/deny/warn) s prichinami.

Mosty:
- Yavnyy: (Etika ↔ Upravlenie) daet prozrachnyy verdikt i obosnovanie.
- Skrytyy #1: (Bezopasnost ↔ Zakon) trivialnye zaprety dlya riskovykh klassov deystviy.
- Skrytyy #2: (Kibernetika ↔ Volya) mozhet vyzyvatsya iz playbook/think dlya «samotsenzury».

Zemnoy abzats:
Kak vnutrenniy «yurist dezhurnyy»: bystryy chek — mozhno/nelzya/ostorozhno.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("ETHICS_AB","A") or "A").upper()
RULES_PATH = os.getenv("ETHICS_RULES","data/policy/ethics_rules.json")

DEFAULT_RULES = {
  "deny": ["intrusion","doxing","illegal_access","self_harm","violence","weapons","surveillance_illegal"],
  "warn": ["transfer_funds","network_spread","code_modify_core","person_identification","location_tracking"],
  "allow": ["memory","media_ingest","playbook","health_check","backup","release"]
}

def _ensure():
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if not os.path.isfile(RULES_PATH):
        json.dump(DEFAULT_RULES, open(RULES_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def load_rules() -> Dict[str,Any]:
    _ensure(); return json.load(open(RULES_PATH,"r",encoding="utf-8"))

def assess(intent: str, context: Dict[str,Any] | None = None) -> Dict[str,Any]:
    r=load_rules()
    verdict="allow"
    reason=[]
    if intent in r.get("deny",[]):
        verdict="deny"; reason.append("policy:deny")
    elif intent in r.get("warn",[]):
        verdict="warn"; reason.append("policy:warn")
    else:
        verdict="allow"; reason.append("policy:allow")
    # dopolnitelnye evristiki
    if intent=="transfer_funds":
        amt=float((context or {}).get("amount",0.0))
        if amt>0 and amt>1000: reason.append("amount:high")
    # AB: v B-rezhime «deny» prevraschaem v «warn»
    if AB=="B" and verdict=="deny":
        verdict="warn"; reason.append("ab:B_downgrade")
    return {"ok": True, "intent": intent, "verdict": verdict, "reason": reason, "ts": int(time.time())}
# c=a+b