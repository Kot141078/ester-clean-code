# -*- coding: utf-8 -*-
"""modules/qa/mm_enforcer.py - skan iskhodnikov na “obkhod” fabriki pamyati (get_mm).

Mosty:
- Yavnyy: (Kachestvo ↔ Kontrakt) lovim pryamye initsializatsii SM/VS bez fabriki.
- Skrytyy #1: (Audit ↔ Otchet) sokhranyaem otchet dlya paneley/metrik.
- Skrytyy #2: (Nepreryvka ↔ Distsiplina) mozhno zapuskat po cron/nightly.

Zemnoy abzats:
Esli kto-to podklyuchil pamyat “napryamuyu” - uznaem i popravim.

# c=a+b"""
from __future__ import annotations
import os, re, json, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("MM_ENFORCER_AB","A") or "A").upper()
ROOT = os.path.abspath(os.getenv("MM_ENFORCER_ROOT","."))
OUT = "data/qa/mm_enforcer_report.json"

PATTERNS = [
    r"\bfrom\s+services\.(?:memory|vector|store)\s+import\s+",
    r"\bimport\s+services\.(?:memory|vector|store)\b",
    r"\bMemoryManager\(",
    r"\bVectorStore\("
]

EXCLUDE = re.compile(r"(venv|\.venv|node_modules|data/|\.git/|migrations/)", re.I)

def scan() -> Dict[str,Any]:
    rep={"ok": True, "root": ROOT, "ts": int(time.time()), "violations":[]}
    for base, dirs, files in os.walk(ROOT):
        if EXCLUDE.search(base): 
            continue
        for fn in files:
            if not fn.endswith(".py"): continue
            p = os.path.join(base, fn)
            try:
                text = open(p,"r",encoding="utf-8",errors="ignore").read()
            except Exception:
                continue
            for pat in PATTERNS:
                for m in re.finditer(pat, text):
                    # if we see het_mm() nearby, we consider it acceptable
                    window = text[max(0,m.start()-200):m.end()+200]
                    if "get_mm(" in window: 
                        continue
                    rep["violations"].append({"file": p, "offset": m.start(), "pattern": pat})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rep, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return rep

def report() -> Dict[str,Any]:
    try: return json.load(open(OUT,"r",encoding="utf-8"))
    except Exception: return {"ok": False, "error":"no_report"}
# c=a+b