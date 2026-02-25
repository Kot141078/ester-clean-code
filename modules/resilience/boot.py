# -*- coding: utf-8 -*-
"""modules/resilience/boot.py - samodiagnostika zapuska i legkiy “repair”.

Mosty:
- Yavnyy: (Inzheneriya ↔ Operatsii) proveryaem direktorii/fayly/politiki/klyuchi.
- Skrytyy #1: (Trust ↔ Politiki) podtyagivaem nedostayuschie katalogi v data/*.
- Skrytyy #2: (Samoobsluzhivanie ↔ Cron) mozhno gonyat raz v sutki.

Zemnoy abzats:
Pered dlinnym puteshestviem - proverili remen, maslo i aptechku.

# c=a+b"""
from __future__ import annotations
import os, json
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

NEED_DIRS = [
    "data/policy", "data/trust", "data/snapshots", "data/forge/backups",
    "data/releases", "data/backup", "data/playbooks"
]
NEED_FILES = [
    ("data/policy/caution_rules.base.json", '{"rules": []}')
]

def status() -> Dict[str,Any]:
    dirs={d: os.path.isdir(d) for d in NEED_DIRS}
    files={p: os.path.isfile(p) for p,_ in NEED_FILES}
    return {"ok": all(dirs.values()) and all(files.values()), "dirs": dirs, "files": files}

def repair() -> Dict[str,Any]:
    for d in NEED_DIRS: os.makedirs(d, exist_ok=True)
    for p,content in NEED_FILES:
        if not os.path.isfile(p):
            open(p,"w",encoding="utf-8").write(content)
    return status()
# c=a+b