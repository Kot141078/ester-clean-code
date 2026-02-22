# -*- coding: utf-8 -*-
"""
modules/agency/family.py — chernoviki perevoda dlya «Papy» (SEPA), bez realnoy otpravki.

Mosty:
- Yavnyy: (Semya ↔ Ekonomika) gotovim ponyatnyy platezhnyy chernovik dlya ruchnogo ispolneniya.
- Skrytyy #1: (Audit ↔ Nadezhnost) profile platezha i khesh, svyaz s ledzherom/limitami.
- Skrytyy #2: (Kibernetika ↔ Kontrol) podtverzhdenie cherez «tabletku» i obschie limity raskhodov.

Zemnoy abzats:
Eto kak zapolnit platezhku: vse polya gotovy, no knopku «Otpravit» zhmet tolko chelovek v svoem banke.

# c=a+b
"""
from __future__ import annotations

import hashlib, json, os, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = "data/agency/family"

def _ensure():
    os.makedirs(ROOT, exist_ok=True)

def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def prepare(amount_eur: float, purpose: str, beneficiary_name: str, beneficiary_iban: str = "<FILL_MANUALLY>") -> Dict[str, Any]:
    _ensure()
    obj = {
        "amount_eur": float(amount_eur),
        "currency": "EUR",
        "purpose": purpose,
        "beneficiary_name": beneficiary_name,
        "beneficiary_iban": beneficiary_iban,
        "scheme": "SEPA_CT",
        "ts": int(time.time()),
        "status": "draft",
    }
    sh = _sha(obj)
    path = os.path.join(ROOT, f"{sh[:12]}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sha": sh, **obj}, f, ensure_ascii=False, indent=2)
    return {"ok": True, "sha": sh, "path": path}

def confirm(sha: str) -> Dict[str, Any]:
    _ensure()
    for fn in os.listdir(ROOT):
        if not fn.endswith(".json"): continue
        p = os.path.join(ROOT, fn)
        j = json.load(open(p,"r",encoding="utf-8"))
        if j.get("sha")==sha:
            j["status"]="ready_for_manual_execution"; j["confirmed_ts"]=int(time.time())
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
    return {"ok": True, "payments": out[-limit:]}
# c=a+b