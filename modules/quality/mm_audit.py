# -*- coding: utf-8 -*-
"""
modules/quality/mm_audit.py — audit obkhodov fabriki pamyati (get_mm) cherez offlayn-skan iskhodnikov.

Mosty:
- Yavnyy: (Kod ↔ Kachestvo) ischem potentsialnye pryamye initsializatsii/obkhody i fiksiruem otchet.
- Skrytyy #1: (Memory ↔ Profile) sokhranyaem «profile» skana, chtoby videt regressii.
- Skrytyy #2: (Mysli ↔ Avtomatizatsiya) vyzyvatsya «voley» po raspisaniyu.

Zemnoy abzats:
Eto «linter so zdravym smyslom»: podsvechivaet mesta, gde mogli oboyti obschiy vkhod k pamyati.

# c=a+b
"""
from __future__ import annotations
import os, json, time, glob, re
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB   = os.getenv("MM_AUDIT_DB","data/quality/mm_audit.json")
SCAN = os.getenv("MM_AUDIT_SCAN","modules/**/*.py,routes/**/*.py,services/**/*.py")

PATTERNS = [
    (r"\bMemoryManager\s*\(", "direct_MemoryManager_ctor"),
    (r"\bVectorStore\s*\(",   "direct_VectorStore_ctor"),
    (r"\bget_mm\s*\(",        "factory_get_mm_call"),  # dlya statistiki
    (r"from\s+services\.mm_access\s+import\s+get_mm", "factory_import")
]

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"reports":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _glob_many(masks: List[str])->List[str]:
    out=[]
    for m in masks:
        for path in glob.glob(m.strip(), recursive=True):
            if path.endswith(".py"): out.append(path)
    return sorted(list(set(out)))

def scan(extra_masks: List[str]|None=None)->Dict[str,Any]:
    masks= list(extra_masks or []) or [x for x in SCAN.split(",") if x.strip()]
    files=_glob_many(masks)
    rep={"ts": int(time.time()), "files": len(files), "findings": []}
    for path in files:
        try:
            txt=open(path,"r",encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        hits=[]
        for rx, kind in PATTERNS:
            if re.search(rx, txt):
                hits.append(kind)
        if hits:
            rep["findings"].append({"path": path, "hits": hits})
    j=_load(); j["reports"].append(rep); _save(j)
    # profile
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm=get_mm(); upsert_with_passport(mm, "mm_audit_scan", {"files": rep["files"], "findings": len(rep["findings"])}, source="quality://mm_audit")
    except Exception:
        pass
    return {"ok": True, "report": rep}

def last_report()->Dict[str,Any]:
    j=_load()
    if not j.get("reports"): return {"ok": True, "report": {}}
    return {"ok": True, "report": j["reports"][-1]}
# c=a+b