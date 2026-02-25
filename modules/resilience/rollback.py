# -*- coding: utf-8 -*-
"""modules/resilience/rollback.py - otkat putey k poslednim bekapam iz forge.

Mosty:
- Yavnyy: (Samoistselenie ↔ Khranenie) ispolzuet bekapy fordzha dlya vosstanovleniya.
- Skrytyy #1: (Trust ↔ Tselostnost) otkat — yavnoe deystvie s otchetom i auditom.
- Skrytyy #2: (Kibernetika ↔ Plan) vyzyvaetsya guard-obertkoy pri provale health.
- Skrytyy #3: (Forge ↔ Bezopasnost) registriruem bekapy s soderzhimym dlya prozrachnosti.

Zemnoy abzats:
Slomalos after pravki? Vernuli predyduschee sostoyanie po rezervnoy kopii - kak “Ctrl+Z” dlya faylov, s versiyami i kheshami, chtoby esli became khuzhe, otkatyvaemsya gratsiozno i ​​s istoriey.

# c=a+b"""
from __future__ import annotations
import os, glob, shutil, json, hashlib, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BACK_DIR = os.getenv("FORGE_BACKUP_DIR", "data/forge/backups")

def _ensure() -> None:
    os.makedirs(BACK_DIR, exist_ok=True)

def _bak_path(path: str, ts: int | None = None) -> str:
    h = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    if ts is None:
        return os.path.join(BACK_DIR, f"{h}_*.json")
    return os.path.join(BACK_DIR, f"{h}_{ts}.json")

def register_backup(path: str, content: str) -> None:
    _ensure()
    ts = int(time.time())
    rec = {"path": path, "content": content, "ts": ts}
    bp = _bak_path(path, ts)
    json.dump(rec, open(bp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def _last_backup_for(path: str, depth: int = 1) -> str | None:
    pattern = _bak_path(path)
    cand = sorted(glob.glob(pattern), key=lambda x: int(x.split('_')[-1].split('.')[0]), reverse=True)
    if len(cand) >= depth:
        return cand[depth - 1]
    return None

def rollback_paths(paths: List[str], depth: int = 1) -> Dict[str, Any]:
    _ensure()
    done = []
    errs = []
    for p in paths or []:
        b = _last_backup_for(p, depth)
        if not b:
            errs.append({"path": p, "error": "backup_not_found"})
            continue
        try:
            rec = json.load(open(b, "r", encoding="utf-8"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(rec.get("content", ""))
            done.append({"path": p, "backup": b})
        except Exception as e:
            errs.append({"path": p, "error": str(e)})
# return {"ok": len(errs) == 0, "done": done, "errors": errs}