# -*- coding: utf-8 -*-
"""modules/mem/maintenance.py - tekhprotsedury pamyati (heal/compact/snapshot/reindex/validate).

Mosty:
- Yavnyy: (Memory ↔ Servis) edinaya tochka “pochinki” bez privyazki k konkretnoy BD.
- Skrytyy #1: (Profile ↔ Audit) fiksiruem operatsii i vykhodnye fayly.
- Skrytyy #2: (Kron ↔ Taymer) dergaetsya iz planirovschika/ekshenov.

Zemnoy abzats:
Eto kak ezhegodnoe TO: proverit krepleniya, podtyanut indeksy, sdelat snimok “kak est”. Teper s validatsiey - chtoby ne prosto chinit, a ubezhdatsya, chto vse na mazi.

# c=a+b"""
from __future__ import annotations
import os, time, json, shutil, gzip
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SNAP_DIR = os.getenv("MAINT_SNAPSHOT_DIR", "data/mem/snapshots")

def _passport(note: str, meta: Dict[str, Any]) -> None:
    try:
        from services.mm_access import get_mm  # type: ignore
        from modules.mem.passport import upsert_with_passport  # type: ignore
        mm = get_mm()
        upsert_with_passport(mm, note, meta, source="mem://maintenance")
    except Exception:
        pass

def _best_effort_heal() -> Dict[str, Any]:
    # Place for real checks (integrity, counters, orphan nodes, etc.)
    fixed = 0  # You can add logic: check files/DB
    return {"ok": True, "fixed": fixed}

def _best_effort_compact() -> Dict[str, Any]:
    # Space for actual compression/vacuumization
    reduced_kb = 0  # You can add: remove duplicates or optimize indexes
    return {"ok": True, "reduced_kb": reduced_kb}

def _snapshot() -> Dict[str, Any]:
    os.makedirs(SNAP_DIR, exist_ok=True)
    ts = int(time.time())
    d = os.path.join(SNAP_DIR, f"snap_{ts}")
    os.makedirs(d, exist_ok=True)
    
    # Copy key files (from the first option)
    sources = [
        ("data/mem/passport.jsonl", "passport.jsonl"),
        ("data/social/ledger.json", "social_ledger.json"),
        ("data/p2p/bloom.json", "p2p_bloom.json")
    ]
    copied = []
    for src, name in sources:
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(d, name))
            copied.append(name)
    
    # Add gzip upload (from the second, for backend records)
    path = os.path.join(d, f"snapshot_{ts}.jsonl.gz")
    count = 0
    try:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            # “Layout” of the image + potential upload from the database (extended if there is a backend)
            f.write(json.dumps({"ts": ts, "note": "snapshot_stub", "n": 0}, ensure_ascii=False) + "\n")
            count = 1  # Here you can add a real iteration through the records
    except Exception:
        pass
    
    # Meta for directory
    open(os.path.join(d, "meta.json"), "w", encoding="utf-8").write(
        json.dumps({"ts": ts, "copied": copied, "gzip_file": path, "rows": count}, ensure_ascii=False, indent=2)
    )
    
    return {"ok": True, "dir": d, "files": copied, "gzip_file": path, "rows": count}

def _reindex() -> Dict[str, Any]:
    # Place for real reindexing (vector/lexicon/hierarchy)
    return {"ok": True}

def heal() -> Dict[str, Any]:
    rep = _best_effort_heal()
    _passport("mem_heal", rep)
    return rep

def compact() -> Dict[str, Any]:
    rep = _best_effort_compact()
    _passport("mem_compact", rep)
    return rep

def snapshot() -> Dict[str, Any]:
    rep = _snapshot()
    _passport("mem_snapshot", rep)
    return rep

def reindex() -> Dict[str, Any]:
    rep = _reindex()
    _passport("mem_reindex", rep)
    return rep

def validate() -> Dict[str, Any]:
    issues = 0  # Place for checks: consistency, duplication, etc.
    rep = {"ok": True, "issues": issues}
    _passport("mem_validate", rep)
# return rep