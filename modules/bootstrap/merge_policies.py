# -*- coding: utf-8 -*-
"""modules/bootstrap/merge_policies.py — sliyanie pravil ostorozhnosti (*caution*) v edinyy fayl.

Mosty:
- Yavnyy: (Politiki ↔ Ispolnenie) daem okhranniku odnu “sshituyu” politiku.
- Skrytyy #1: (Audit ↔ Prozrachnost) vkhody/vykhody fiksiruyutsya na diske.
- Skrytyy #2: (Inzheneriya ↔ Nadezhnost) zaschischaemsya ot polomki pri mnozhestve .extend faylov.

Zemnoy abzats:
Sobrali kusochki “ne zhgi krasnuyu knopku” v odin svod - menshe shansov oshibitsya.

# c=a+b"""
from __future__ import annotations
import json, os, glob
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MERGED = os.getenv("APP_POLICY_MERGED","data/policy/caution_rules.merged.json")

def merge() -> Dict[str,Any]:
    os.makedirs(os.path.dirname(MERGED), exist_ok=True)
    base=[]
    for fn in glob.glob("data/policy/caution_rules*.json"):
        try:
            j=json.load(open(fn,"r",encoding="utf-8"))
            base += j.get("rules",[])
        except Exception:
            continue
    # dedup by (pattern,method)
    seen=set(); out=[]
    for r in base:
        key=(r.get("pattern",""), r.get("method","GET"))
        if key in seen: continue
        seen.add(key); out.append(r)
    obj={"rules": out, "count": len(out)}
    json.dump(obj, open(MERGED,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "merged": MERGED, "count": len(out)}
# c=a+b