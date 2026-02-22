# -*- coding: utf-8 -*-
"""
modules/sos/kit.py — SOS-konfig i eskalatsiya (plan deystviy).

Mosty:
- Yavnyy: (Zabota ↔ Operatsii) khranit kontakty Papy/adresa/porogi srabatyvaniya.
- Skrytyy #1: (Etika ↔ Ostorozhnost) formiruet plan, ne sovershaya vneshnikh deystviy.
- Skrytyy #2: (Memory ↔ Audit) logiruet intsidenty (JSONL).

Zemnoy abzats:
Trevozhnaya knopka: zapisat intsident i vydat ponyatnyy plan — kogo/kak uvedomit.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CFG = os.getenv("SOS_DB","data/sos/config.json")
INC = os.getenv("INCIDENT_DB","data/sos/incidents.jsonl")

DEFAULT = {
  "contacts": {"papa":"+000000"},
  "address": "unknown",
  "policies": {
    "medical": {"call_threshold": 0.8, "notify":["papa"]},
    "safety":  {"call_threshold": 0.7, "notify":["papa"]}
  }
}

def _ensure():
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    if not os.path.isfile(CFG):
        json.dump(DEFAULT, open(CFG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(INC), exist_ok=True)
    if not os.path.isfile(INC): open(INC,"w",encoding="utf-8").close()

def get_config() -> Dict[str,Any]:
    _ensure(); return json.load(open(CFG,"r",encoding="utf-8"))

def set_config(obj: Dict[str,Any]) -> Dict[str,Any]:
    _ensure(); cur=get_config(); cur.update(obj or {})
    json.dump(cur, open(CFG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "config": cur}

def assess(signal: str, severity: float, note: str = "", who: str | None = None) -> Dict[str,Any]:
    _ensure()
    cfg=get_config()
    kind = "medical" if "pain" in (signal or "") or "heart" in (signal or "") else "safety"
    pol = cfg.get("policies",{}).get(kind, {"call_threshold":0.8,"notify":[]})
    plan = []
    if severity >= float(pol.get("call_threshold",0.8)):
        plan.append({"act":"call_emergency","details":{"region": cfg.get("address","unknown")}})
    for k in (pol.get("notify") or []):
        if k in cfg.get("contacts",{}):
            plan.append({"act":"notify","to":k,"value":cfg["contacts"][k]})
    if not plan:
        plan.append({"act":"observe","details":{"advice":"monitor symptoms"}})
    return {"ok": True, "kind": kind, "plan": plan, "severity": severity, "address": cfg.get("address","unknown"), "who": who}

def trigger(event: Dict[str,Any]) -> Dict[str,Any]:
    _ensure()
    ev={"ts": int(time.time()), **(event or {})}
    with open(INC,"a",encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    rep=assess(str(event.get("kind","")), float(event.get("severity",0.0)), str(event.get("note","")), str(event.get("who","")))
    return {"ok": True, "incident": ev, "plan": rep.get("plan"), "advice": "execute plan manually or via approved connectors"}
# c=a+b