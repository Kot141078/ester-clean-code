# -*- coding: utf-8 -*-
"""modules/backup/snapshot.py - prostye backup: ZIP + manifest + retention.

Mosty:
- Yavnyy: (FS ↔ Survival) sobiraem snapshot vazhnykh katalogov s kheshem i opisaniem.
- Skrytyy #1: (Passport ↔ Prozrachnost) sozdaem zapis o bekape.
- Skrytyy #2: (ABSlots/P2P ↔ Rasprostranenie) ZIP prigoden dlya perenosa/samosborki.

Zemnoy abzats:
Kak “arkhiv nochi”: zapakovali nuzhnye papki, podpisali, ostavili tolko svezhie - ostalnoe vybrosili.

# c=a+b"""
from __future__ import annotations
import os, time, json, hashlib, zipfile, glob, shutil
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BACKUP_DIR=os.getenv("BACKUP_DIR","data/backups")
KEEP=int(os.getenv("BACKUP_KEEP","14") or "14")
SNAPSHOT_DIRS=[p.strip() for p in (os.getenv("SNAPSHOT_DIRS","data/passport,data/stt,data/portfolio,data/opps,slots").split(",")) if p.strip()]

os.makedirs(BACKUP_DIR, exist_ok=True)

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "backup://snapshot")
    except Exception:
        pass

def _sha256(path: str)->str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _manifest_of(zip_path: str, label: str, dirs: List[str])->Dict[str,Any]:
    return {"file": os.path.abspath(zip_path), "label": label, "t": int(time.time()), "dirs": dirs, "sha256": _sha256(zip_path)}

def snapshot(dirs: List[str]|None=None, label: str|None=None)->Dict[str,Any]:
    ds=list(dirs or SNAPSHOT_DIRS)
    t=int(time.time())
    zip_path=os.path.join(BACKUP_DIR, f"snapshot_{t}{('_'+label) if label else ''}.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for d in ds:
            if not os.path.exists(d): continue
            base=d.rstrip("/").rstrip("\\")
            for root, _, files in os.walk(d):
                for n in files:
                    fp=os.path.join(root,n)
                    arc=os.path.join(base, os.path.relpath(fp, d))
                    try: z.write(fp, arc)
                    except Exception: pass
    man=_manifest_of(zip_path, label or "", ds)
    open(zip_path+".manifest.json","w",encoding="utf-8").write(json.dumps(man, ensure_ascii=False, indent=2))
    # retention
    files=sorted(glob.glob(os.path.join(BACKUP_DIR,"snapshot_*.zip")), key=os.path.getmtime, reverse=True)
    for old in files[KEEP:]:
        try:
            os.remove(old)
            if os.path.isfile(old+".manifest.json"): os.remove(old+".manifest.json")
        except Exception: pass
    _passport("backup_done", {"file": zip_path, "size": os.path.getsize(zip_path)})
    return {"ok": True, "zip": zip_path, "manifest": zip_path+".manifest.json"}

def status()->Dict[str,Any]:
    files=sorted(glob.glob(os.path.join(BACKUP_DIR,"snapshot_*.zip")), key=os.path.getmtime, reverse=True)
    total=sum((os.path.getsize(p) for p in files), 0)
    return {"ok": True, "count": len(files), "total_bytes": total, "dir": BACKUP_DIR, "keep": KEEP, "files": files[:20]}
# c=a+b