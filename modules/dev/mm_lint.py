# -*- coding: utf-8 -*-
"""modules/dev/mm_lint.py - lint "zhestkoy tochki vkhoda k pamyati": prinuzhdenie get_mm().

Mosty:
- Yavnyy: (Kod ↔ Pravilo) nakhodit podozritelnye obrascheniya k pamyati/vektornym BD vne fabriki.
- Skrytyy #1: (Metriki ↔ Distsiplina) vydaet otchet i schitaet narusheniya.
- Skrytyy #2: (Plan ↔ Refaktoring) otchet mozhno sokhranit i proytis po faylam.

Zemnoy abzats:
This is how “revizor”: ischet pryamye new MemoryManager()/pryamye vyzovy storadzhey i napominaet idti cherez fabriku get_mm().

# c=a+b"""
from __future__ import annotations
import os, re, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.getenv("MM_LINT_ROOT",".")
DB   = os.getenv("MM_LINT_DB","data/dev/mm_lint.json")

SUSPECT_PATTERNS = [
    r"\bMemoryManager\s*\(",
    r"\bChroma(DB)?\s*\(",
    r"\bLance(DB)?\s*\(",
    r"\bFAISS\s*\(",
    r"\bVectorStore\s*\(",
    r"\bnew\s+MemoryManager\b"
]
ALLOWLIST = [
    "services/mm_access.py",  # there's a factory here
    "modules/dev/mm_lint.py"
]

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)

def _scan()->dict:
    sus=[]
    rx=[re.compile(p) for p in SUSPECT_PATTERNS]
    for base,_,files in os.walk(ROOT):
        for f in files:
            if not f.endswith(".py"): continue
            path=os.path.join(base,f)
            rel=path.replace("\\","/")
            if any(rel.endswith(a) for a in ALLOWLIST): continue
            try:
                txt=open(path,"r",encoding="utf-8",errors="ignore").read()
            except Exception:
                continue
            for r in rx:
                if r.search(txt):
                    sus.append(rel); break
    return {"ok": True, "root": ROOT, "suspects": sorted(sus), "count": len(sus)}

def run()->dict:
    rep=_scan()
    _ensure()
    json.dump(rep, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return rep
# c=a+b