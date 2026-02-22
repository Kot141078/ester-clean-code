# -*- coding: utf-8 -*-
"""
modules/agency/hiring.py — bezopasnye chernoviki nayma (brify), bez vneshney publikatsii.

Mosty:
- Yavnyy: (Lyudi ↔ Proekt) formiruem ponyatnye TZ dlya zadach.
- Skrytyy #1: (Audit ↔ Nadezhnost) profile (sha, ts) i status (draft/approved/posted) bez integratsiy.
- Skrytyy #2: (Ekonomika ↔ Kontrol) byudzhety brifov sopostavimy s ledzherom/limitami.

Zemnoy abzats:
Eto kak napisat obyavlenie na doske — poka na bumage, bez rassylki; potom operator reshit, gde i kak publikovat.

# c=a+b
"""
from __future__ import annotations

import hashlib, json, os, time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = "data/agency/hiring/briefs"

def _ensure():
    os.makedirs(ROOT, exist_ok=True)

def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def draft(title: str, description: str, skills: List[str], budget_eur: float, duration: str) -> Dict[str, Any]:
    _ensure()
    obj = {
        "title": title, "description": description, "skills": skills,
        "budget_eur": float(budget_eur), "duration": duration,
        "ts": int(time.time()), "status": "draft"
    }
    sh = _sha(obj)
    path = os.path.join(ROOT, f"{sh[:12]}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sha": sh, **obj}, f, ensure_ascii=False, indent=2)
    return {"ok": True, "sha": sh, "path": path}

def approve(sha: str) -> Dict[str, Any]:
    _ensure()
    for fn in os.listdir(ROOT):
        if not fn.endswith(".json"): continue
        p = os.path.join(ROOT, fn)
        j = json.load(open(p,"r",encoding="utf-8"))
        if j.get("sha")==sha:
            j["status"]="approved"; j["approved_ts"]=int(time.time())
            json.dump(j, open(p,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
            return {"ok": True, "sha": sha, "path": p}
    return {"ok": False, "error":"not found"}

def list_all(limit: int = 200) -> Dict[str, Any]:
    _ensure()
    out = []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".json"): continue
        p = os.path.join(ROOT, fn)
        out.append(json.load(open(p,"r",encoding="utf-8")))
    return {"ok": True, "briefs": out[-limit:]}
# c=a+b