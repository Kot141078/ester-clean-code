# -*- coding: utf-8 -*-
"""modules/vision/adapt_triggers.py - adaptivnye triggery (samonastroyka porogov/yakorey).

Funktsii:
- keep_observation(kind, payload) — kladem nablyudenie v JSONL (hit/miss, threshold, kontekst okna).
- current_threshold() — daet robastnyy threshold (mediana po uspeshnym ± IQR zaschita).
- wrap_threshold(value) — esli value == "auto" -> podstavlyaet current_threshold().

Khranilische:
- data/vision/adapt/template_obs.jsonl — odna zapis na nablyudenie.

Integratsia:
- modules/vision/triggers.py pri kind="template_match" i threshold == "auto"
  vyzyvaet adapt.wrap_threshold("auto"), poluchaya chislo.

MOSTY:
- Yavnyy: (Nablyudenie ↔ Porog) sreda sama podskazyvaet, where granitsa srabatyvaniya.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) mediana/IQR vmesto “magicheskogo” chisla.
- Skrytyy #2: (Kibernetika ↔ Obuchenie) kazhdoe srabatyvanie uluchshaet posleduyuschie.

ZEMNOY ABZATs:
Obychnyy JSONL; ustoychivye statistiki, nikakikh vneshnikh BD i demonov.

# c=a+b"""
from __future__ import annotations
import os, json, statistics
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "vision", "adapt")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "template_obs.jsonl")

def keep_observation(result: str, thr: float, meta: Dict[str, Any]|None=None) -> Dict[str, Any]:
    row = {"result": str(result), "thr": float(thr), "meta": meta or {}}
    with open(FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}

def _load_all() -> List[Dict[str, Any]]:
    if not os.path.exists(FILE): return []
    out: List[Dict[str, Any]] = []
    with open(FILE, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def current_threshold(default: float = 0.78) -> float:
    data = [x for x in _load_all() if x.get("result") == "hit"]
    if len(data) < 3:
        return float(default)
    vals = sorted(float(x.get("thr", default)) for x in data if isinstance(x.get("thr"), (int,float)))
    if not vals: return float(default)
    # robust: median, then "raised" by 10% of the interquartile range
    med = statistics.median(vals)
    q1  = statistics.median(vals[:len(vals)//2])
    q3  = statistics.median(vals[(len(vals)+1)//2:])
    iqr = max(0.0, q3 - q1)
    return float(min(0.999, max(0.5, med + 0.1*iqr)))

def wrap_threshold(value: str|float|None, default: float = 0.78) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip().lower() == "auto":
        return current_threshold(default=default)
    return float(default)