# -*- coding: utf-8 -*-
"""
modules/audit/attention_log.py — zhurnal vnimaniya (taymlayn tseley i deystviy).

Khranilische: data/audit/attention/log.jsonl (po odnoy stroke JSON na sobytie)
API:
- append(event:str, detail:dict)
- list_last(N) -> poslednie sobytiya
- dump_all() -> polnyy spisok (ostorozhno)

MOSTY:
- Yavnyy: (Vnimanie ↔ Memory) fiksiruem kuda smotreli i chto delali.
- Skrytyy #1: (Infoteoriya ↔ Analitika) gotovo dlya post-analiza.
- Skrytyy #2: (Kibernetika ↔ Uluchshenie) vidno, chto/kogda zapuskalo deystvie.

ZEMNOY ABZATs:
Obychnyy JSONL. Zapolnyayut: triggery, «ochki vnimaniya», rezhisser. Bez vneshnikh BD.

# c=a+b
"""
from __future__ import annotations
import os, json, time
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR = os.path.join(ROOT, "data", "audit", "attention")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "log.jsonl")

def append(event: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    row = {"ts": int(time.time()), "event": event, "detail": detail or {}}
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}

def list_last(n: int = 200) -> List[Dict[str, Any]]:
    if not os.path.exists(FILE):
        return []
    res: List[Dict[str, Any]] = []
    with open(FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                res.append(json.loads(line.strip()))
            except Exception:
                pass
    return res[-n:]

def dump_all() -> List[Dict[str, Any]]:
    return list_last(10**9)