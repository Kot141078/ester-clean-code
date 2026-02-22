# -*- coding: utf-8 -*-
"""
modules/agency/ledger.py — prostoy ledzher resursov i deneg dlya Ester (dokhody/raskhody/balansy/limity).

Mosty:
- Yavnyy: (Ekonomika ↔ Myshlenie) plan opiraetsya na realnye resursy i limity trat.
- Skrytyy #1: (Infoteoriya ↔ Audit) JSONL-zhurnal s provenansom i sha256 dlya vosproizvodimosti.
- Skrytyy #2: (Kibernetika ↔ Kontrol) dnevnye/mesyachnye kapy i «tabletka»-overrayd (cherez routes/agency).

Zemnoy abzats:
Eto kassa i sklad: znaem, skolko est deneg/resursov, otkuda prishlo i kuda potratit bezopasno.

# c=a+b
"""
from __future__ import annotations

import hashlib, json, os, time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = "data/agency"
LEDGER = os.path.join(ROOT, "ledger.jsonl")

def _ensure():
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.isfile(LEDGER):
        open(LEDGER, "a", encoding="utf-8").close()

def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def _append(entry: Dict[str, Any]) -> Dict[str, Any]:
    _ensure()
    entry["ts"] = int(time.time())
    entry["sha256"] = _sha(entry)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry

def entries(limit: int = 500) -> List[Dict[str, Any]]:
    _ensure()
    out: List[Dict[str, Any]] = []
    with open(LEDGER, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    return out[-limit:] if limit>0 else out

def balances() -> Dict[str, Any]:
    # Denezhnye (EUR) i "naturalnye" resursy (proizvolnye edinitsy)
    cash_eur = 0.0
    resources: Dict[str, float] = {}
    for e in entries(limit=0):
        if e.get("kind") == "income" and e.get("currency") == "EUR":
            cash_eur += float(e.get("amount", 0))
        if e.get("kind") == "expense" and e.get("currency") == "EUR":
            cash_eur -= float(e.get("amount", 0))
        if e.get("kind") == "resource_add":
            k = e.get("name","")
            resources[k] = resources.get(k, 0.0) + float(e.get("qty",0))
        if e.get("kind") == "resource_consume":
            k = e.get("name","")
            resources[k] = resources.get(k, 0.0) - float(e.get("qty",0))
    # okruglim do kopeek
    cash_eur = float(f"{cash_eur:.2f}")
    return {"cash_eur": cash_eur, "resources": resources}

def add_income(amount: float, currency: str, source: str, meta: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return _append({"kind":"income","amount":float(amount),"currency":currency,"source":source,"meta":meta or {}})

def add_expense(amount: float, currency: str, purpose: str, meta: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return _append({"kind":"expense","amount":float(amount),"currency":currency,"purpose":purpose,"meta":meta or {}})

def add_resource(name: str, qty: float, unit: str, meta: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return _append({"kind":"resource_add","name":name,"qty":float(qty),"unit":unit,"meta":meta or {}})

def consume_resource(name: str, qty: float, unit: str, meta: Optional[Dict[str,Any]]=None) -> Dict[str, Any]:
    return _append({"kind":"resource_consume","name":name,"qty":float(qty),"unit":unit,"meta":meta or {}})

def spend_allowed(eur: float, daily_cap: float, monthly_cap: float, pill_armed: bool) -> Dict[str, Any]:
    """
    Prostaya politika: razreshit tratu, esli <= daily/monthly kapov; inache — tolko s «tabletkoy».
    """
    now = int(time.time())
    day_start = now - 24*3600
    mon_start = now - 30*24*3600
    day_sum = 0.0
    mon_sum = 0.0
    for e in entries(limit=0):
        if e.get("kind")=="expense" and e.get("currency")=="EUR":
            ts = int(e.get("ts",0))
            amt = float(e.get("amount",0))
            if ts >= day_start: day_sum += amt
            if ts >= mon_start: mon_sum += amt
    new_day = day_sum + eur
    new_mon = mon_sum + eur
    ok = (new_day <= daily_cap and new_mon <= monthly_cap) or pill_armed
    return {"ok": ok, "day_after": round(new_day,2), "mon_after": round(new_mon,2), "pill": pill_armed}
# c=a+b