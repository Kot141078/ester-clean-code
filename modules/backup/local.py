# -*- coding: utf-8 -*-
"""modules/backup/local.py - prostye lokalnye bekapy vybrannykh korney v spisok tselevykh direktoriy.

Mosty:
- Yavnyy: (Rezerv ↔ Disk) zerkalim vazhnye katalogi.
- Skrytyy #1: (Infoteoriya ↔ Dedup) kopiruem tolko izmenennye po sha256/razmeru.
- Skrytyy #2: (Ustoychivost ↔ Planirovschik) mozhno vyzyvat iz cron.

Zemnoy abzats:
“Spryatat kopiyu v shkafu”: bystroe lokalnoe dublirovanie bez oblakov.

# c=a+b"""
from __future__ import annotations
import os, json, hashlib, shutil
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("BACKUP_DB","data/backup/targets.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"targets":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def get_targets() -> Dict[str,Any]:
    _ensure()
    return json.load(open(DB,"r",encoding="utf-8"))

def set_targets(targets: List[str]) -> Dict[str,Any]:
    _ensure()
    for t in targets or []:
        os.makedirs(t, exist_ok=True)
    json.dump({"targets": targets}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "targets": targets}

def _walk(roots: List[str]) -> List[str]:
    files=[]
    for r in roots or []:
        if os.path.isfile(r): files.append(r)
        elif os.path.isdir(r):
            for base,_,fs in os.walk(r):
                for fn in fs:
                    files.append(os.path.join(base,fn))
    return files

def _sha(p: str) -> str:
    import hashlib
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for ch in iter(lambda: f.read(1<<20), b""): h.update(ch)
    return h.hexdigest()

def run_backup(roots: List[str]) -> Dict[str,Any]:
    _ensure()
    t=json.load(open(DB,"r",encoding="utf-8")).get("targets",[])
    if not t: return {"ok": False, "error":"no_targets"}
    files=_walk(roots)
    copied=0; skipped=0; errs=[]
    for dst in t:
        for p in files:
            try:
                rel=p
                out=os.path.join(dst, rel)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                if os.path.exists(out):
                    if os.path.getsize(out)==os.path.getsize(p):
                        if _sha(out)==_sha(p):
                            skipped+=1; continue
                shutil.copy2(p, out)
                copied+=1
            except Exception as e:
                errs.append({"path": p, "dst": dst, "error": str(e)})
    return {"ok": len(errs)==0, "copied": copied, "skipped": skipped, "errors": errs}
# c=a+b