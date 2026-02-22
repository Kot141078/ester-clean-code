# -*- coding: utf-8 -*-
"""
modules/policy/legal_guard.py — legalnyy storozh: proverka zadach po JSON-pravilam.

Mosty:
- Yavnyy: (Plan ↔ Politika) bystryy otvet «mozhno/nelzya/vnimatelno» s prichinami.
- Skrytyy #1: (RBAC/Pilyuli ↔ Ostorozhnost) integriruetsya s sistemoy riskov.
- Skrytyy #2: (Profile ↔ Audit) rezultaty mozhno zhurnalirovat.

Zemnoy abzats:
Kak vnutrenniy yurist: na vkhod plan deystviya, na vykhod — svetofor i korotkaya pamyatka, chto imenno opasno.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

RULES_PATH=os.getenv("LEGAL_RULES","data/policy/legal_rules.json")

_DEFAULT_RULES={
  "deny": [
    {"kind":"financial_transfer", "rule":"no_self_discovery_accounts", "reason":"Nelzya samostoyatelno iskat chuzhie scheta/identifikatory."},
    {"kind":"surveillance", "rule":"no_tracking_people", "reason":"Nelzya otslezhivat lyudey, ikh mestopolozhenie ili scheta."}
  ],
  "warn": [
    {"kind":"web_scrape", "rule":"respect_robots_and_tos", "reason":"Proverit robots.txt/ToS/kvoty; sobirat tolko razreshennoe."},
    {"kind":"content_publish", "rule":"copyright_check", "reason":"Proverit avtorskie prava i litsenzii na iskhodniki."}
  ],
  "allow": [
    {"kind":"subtitle_extract", "rule":"public_or_user_owned", "reason":"S publichnykh istochnikov ili po zaprosu polzovatelya."}
  ]
}

def _ensure():
    os.makedirs(os.path.dirname(RULES_PATH), exist_ok=True)
    if not os.path.isfile(RULES_PATH):
        json.dump(_DEFAULT_RULES, open(RULES_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(RULES_PATH,"r",encoding="utf-8"))

def check(task: Dict[str,Any])->Dict[str,Any]:
    """
    task: {"kind":"...", "target":"...", "notes":"..."}
    """
    rules=_load()
    kind=str((task or {}).get("kind","")).strip().lower()
    verdict="allow"; reasons=[]
    for r in rules.get("deny",[]):
        if r.get("kind","").lower()==kind:
            return {"ok": True, "verdict":"deny", "reasons":[r.get("reason","")]}
    for r in rules.get("warn",[]):
        if r.get("kind","").lower()==kind:
            verdict="warn"; reasons.append(r.get("reason",""))
    if verdict=="allow":
        for r in rules.get("allow",[]):
            if r.get("kind","").lower()==kind:
                reasons.append(r.get("reason",""))
    return {"ok": True, "verdict": verdict, "reasons": reasons}
# c=a+b