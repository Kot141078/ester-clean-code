# -*- coding: utf-8 -*-
"""modules/mm/lint.py - “zhestche prinudit get_mm()”: poisk obkhodov fabriki pamyati (best-effort).

Mosty:
- Yavnyy: (Kachestvo ↔ Memory) podsvetka place v kode, where initsializiruyut pamyat napryamuyu.
- Skrytyy #1: (Audit ↔ Prozrachnost) otchet v JSON dlya bystroy pravki.
- Skrytyy #2: (Kibernetika ↔ Avtonomiya) mozhno privyazat k cron kak lint-shag.

Zemnoy abzats:
Nakhodim "dyrki" gde lezut mimo `get_mm()` i zakryvaem ikh.
# c=a+b"""
from __future__ import annotations
import os, re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PATTERNS = [
    r"\bChromaDB\s*\(",
    r"\bLanceDB\s*\(",
    r"\bVectorStore\s*\(",
    r"\bMemoryManager\s*\(",
    r"from\s+services\.memory\s+import\s+",
]

def scan(paths: List[str] | None = None) -> Dict[str,Any]:
    roots = paths or ["modules","routes","services"]
    rep=[]
    for root in roots:
        if not os.path.isdir(root): continue
        for base,_,files in os.walk(root):
            for fn in files:
                if not fn.endswith(".py"): continue
                p = os.path.join(base, fn)
                try:
                    t = open(p,"r",encoding="utf-8",errors="ignore").read()
                except Exception:
                    continue
                for pat in PATTERNS:
                    if re.search(pat, t):
                        rep.append({"path": p, "pattern": pat})
                        break
    return {"ok": True, "violations": rep, "count": len(rep)}
# c=a+b