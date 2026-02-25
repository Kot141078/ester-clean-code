# -*- coding: utf-8 -*-
"""modules/crawl/policy.py - lokalnye pravila kroulinga: user-agent, zaderzhki, litsenzii, allow/deny po domenam.

Mosty:
- Yavnyy: (Krouling ↔ Zakonnost) tsentralizovannaya politika dlya vsekh buduschikh kraulerov.
- Skrytyy #1: (Infoteoriya ↔ Audit) fayl s pravilami i yavnym user-agent.
- Skrytyy #2: (Kibernetika ↔ Limity) zaderzhki i denay-listy predotvraschayut blokirovki/iski.

Zemnoy abzats:
Bumazhnaya “instruktsiya po vezhlivomu sboru”: who is mine, s kakoy chastotoy khodim i kuda ne lezem.

# c=a+b"""
from __future__ import annotations
import json, os, time, urllib.parse as urlp
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CRAWL_AB = (os.getenv("CRAWL_AB","A") or "A").upper()
RULES = os.getenv("CRAWL_SITE_RULES","data/crawl/site_rules.json")

DEFAULT = {
  "user_agent": "EsterResearchBot/1.0 (+contact: local; respectful; no scraping of paywalled content)",
  "default_delay_ms": 5000,
  "domains": {
    "default": {"allow": True, "delay_ms": 5000, "license": "unknown"},
    "example.com": {"allow": True, "delay_ms": 3000, "license": "permissive"},
    "kinovibe.vip": {"allow": False, "delay_ms": 0, "license": "unknown"}
  }
}

def _ensure():
    os.makedirs(os.path.dirname(RULES), exist_ok=True)
    if not os.path.isfile(RULES):
        json.dump(DEFAULT, open(RULES,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def check(url: str, purpose: str = "research") -> Dict[str, Any]:
    _ensure()
    pol = json.load(open(RULES,"r",encoding="utf-8"))
    host = urlp.urlparse(url).hostname or ""
    dom = (pol.get("domains") or {}).get(host) or (pol.get("domains") or {}).get("default") or {}
    allow = bool(dom.get("allow", True))
    delay = int(dom.get("delay_ms", pol.get("default_delay_ms", 5000)))
    ua = pol.get("user_agent","EsterResearchBot/1.0")
    if CRAWL_AB == "B":
        allow = True
    return {"ok": True, "url": url, "allow": allow, "delay_ms": delay, "user_agent": ua, "license": dom.get("license","unknown"), "purpose": purpose}
# c=a+b