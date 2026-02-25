# -*- coding: utf-8 -*-
"""modules/subconscious - “podsoznanie” Ester (mikro-scaner pamyati).

MOSTY:
- (Yavnyy) tick(limit=500) -> {"scanned", "keywords"}; status() -> last run.
- (Skrytyy #1) Rabotaet offlayn: chitaet data/mem/**, schitaet chastye tokeny.
- (Skrytyy #2) Pishet state v data/subconscious/status.json (gotovo dlya watchdog).

ZEMNOY ABZATs:
Kak pylesos fona: probezhalsya po pamyati, podnyal chastye “temy” - mozgu legche dumat.

# c=a+b"""
from __future__ import annotations
import os, json, glob, re, time, collections
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BASE = "data/subconscious"
os.makedirs(BASE, exist_ok=True)
STATUS = os.path.join(BASE, "status.json")

def _norm(txt: str):
    txt = txt.lower()
    return [t for t in re.split(r"[^a-za-ya0-9e]+", txt) if t]

def _save(st: Dict[str, Any]):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)

def status() -> Dict[str, Any]:
    try:
        with open(STATUS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ok": True, "last_ts": 0, "keywords": []}

def tick(limit: int = 500) -> Dict[str, Any]:
    cnt = collections.Counter()
    scanned = 0
    for fp in glob.glob("data/mem/**/*.json", recursive=True):
        scanned += 1
        if scanned > limit:
            break
        try:
            with open(fp, "r", encoding="utf-8") as f:
                j = json.load(f)
            for w in _norm(j.get("text","")):
                if len(w) >= 3:
                    cnt[w] += 1
        except Exception:
            continue
    top = [{"t": w, "n": n} for w, n in cnt.most_common(32)]
    st = {"ok": True, "last_ts": int(time.time()), "scanned": scanned, "keywords": top}
    _save(st)
    return st
# c=a+b