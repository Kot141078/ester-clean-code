# -*- coding: utf-8 -*-
"""modules/dr/dr321.py - offsayt-rezerv po pravilu 3-2-1: kopii snapshotov v otdelnuyu zonu s retenshnom.

Mosty:
- Yavnyy: (Nadezhnost ↔ Khranenie) perenosim .tar.gz/.sig.json v OFFSITE_DIR, derzhim poslednie N.
- Skrytyy #1: (Infoteoriya ↔ Audit) sveryaem sha256 s manifesta, spisok i proverka dostupnosti.
- Skrytyy #2: (Vyzhivanie ↔ Samosoborka) restore vozvraschaet arkhiv obratno v osnovnuyu zonu dlya otkata.

Zemnoy abzats:
Esli osnovnoy disk “die” - kopiya lezhit ryadom, no otdelno. Kholodnaya prostaya strakhovka.

# c=a+b"""
from __future__ import annotations
import os, shutil, json
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SNAP_DIR = os.getenv("SELF_SNAPSHOT_DIR","data/self/snapshots")
OFF_DIR = os.getenv("OFFSITE_DIR","data/offsite")
KEEP = int(os.getenv("OFFSITE_KEEP","7") or "7")
DR_AB = (os.getenv("DR_AB","A") or "A").upper()

def _ensure():
    os.makedirs(OFF_DIR, exist_ok=True)

def list_offsite() -> Dict[str, Any]:
    _ensure()
    items = sorted([fn for fn in os.listdir(OFF_DIR) if fn.endswith(".tar.gz")])
    return {"ok": True, "items": items}

def run_backup() -> Dict[str, Any]:
    _ensure()
    copied = []
    for fn in sorted([f for f in os.listdir(SNAP_DIR) if f.endswith(".tar.gz")]):
        src = os.path.join(SNAP_DIR, fn)
        dst = os.path.join(OFF_DIR, fn)
        if not os.path.isfile(dst):
            if DR_AB == "A":
                shutil.copy2(src, dst)
                # next to the signature/manifest - if there is one, we’ll copy it too
                for extra in (f"{fn}.manifest.json", f"{fn}.sig.json"):
                    p = os.path.join(SNAP_DIR, extra)
                    if os.path.isfile(p): shutil.copy2(p, os.path.join(OFF_DIR, extra))
            copied.append(fn)
    # retenshn
    archs = sorted([f for f in os.listdir(OFF_DIR) if f.endswith(".tar.gz")])
    if len(archs) > KEEP:
        drop = archs[0:len(archs)-KEEP]
        for fn in drop:
            try:
                os.remove(os.path.join(OFF_DIR, fn))
                for extra in (f"{fn}.manifest.json", f"{fn}.sig.json"):
                    p = os.path.join(OFF_DIR, extra)
                    if os.path.isfile(p): os.remove(p)
            except Exception:
                pass
    return {"ok": True, "copied": copied, "kept": KEEP, **list_offsite()}

def restore(archive: str) -> Dict[str, Any]:
    _ensure()
    src = os.path.join(OFF_DIR, archive)
    if not os.path.isfile(src):
        return {"ok": False, "error":"not_found"}
    dst = os.path.join(SNAP_DIR, archive)
    shutil.copy2(src, dst)
    # podpisi/manifest
    for extra in (f"{archive}.manifest.json", f"{archive}.sig.json"):
        p = os.path.join(OFF_DIR, extra)
        if os.path.isfile(p): shutil.copy2(p, os.path.join(SNAP_DIR, extra))
    return {"ok": True, "restored": archive}
# c=a+b