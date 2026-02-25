# -*- coding: utf-8 -*-
"""modules/policy/papa_priority.py - Politika prioriteta Papy: vesa, “tabletka”, sovety planirovschikam/koshelku.

Mosty:
- Yavnyy: (Myshlenie ↔ Ekonomika) vydaem bias dlya kaskada/agentstva: bolshe vesa zadacham, veduschim k blagu Papy.
- Skrytyy #1: (Kibernetika ↔ Kontrol) prioritet upravlyaem, a spornye operatsii trebuyut “tabletku”.
- Skrytyy #2: (Memory ↔ Audit) sostoyanie khranitsya v fayle s metadannymi i metkoy family_sensitive.

Zemnoy abzats:
Eto regulyator gromkosti: naskolko silno “podkruchivat” plan i byudzhet v polzu Papy - i na kakoy srok.

# c=a+b"""
from __future__ import annotations
import json, os, time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = (os.getenv("PAPA_AB","A") or "A").upper()
PATH = os.getenv("PAPA_POLICY_PATH","data/policy/papa_policy.json")

def _load() -> Dict[str, Any]:
    try:
        return json.load(open(PATH,"r",encoding="utf-8"))
    except Exception:
        return {"priority": 1.0, "money_bias": 0.8, "task_bias": 0.9, "pill": {"armed": False, "until": 0}, "ts": int(time.time())}

def _save(st: Dict[str, Any]):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(st, open(PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def status() -> Dict[str, Any]:
    st = _load()
    # avto-razoruzhenie tabletki
    if st["pill"]["armed"] and int(time.time()) > int(st["pill"]["until"]):
        st["pill"] = {"armed": False, "until": 0}; _save(st)
    return {"ok": True, **st, "ab": AB}

def set_policy(priority: float | None = None, money_bias: float | None = None, task_bias: float | None = None) -> Dict[str, Any]:
    if AB == "B":
        return {"ok": False, "error": "PAPA_AB=B"}
    st = _load()
    if priority is not None: st["priority"] = max(0.0, min(1.0, float(priority)))
    if money_bias is not None: st["money_bias"] = max(0.0, min(1.0, float(money_bias)))
    if task_bias is not None: st["task_bias"] = max(0.0, min(1.0, float(task_bias)))
    st["ts"] = int(time.time()); _save(st)
    return {"ok": True, **st}

def pill(arm: bool, ttl_sec: int = 300) -> Dict[str, Any]:
    st = _load()
    if arm:
        st["pill"] = {"armed": True, "until": int(time.time()) + max(30, int(ttl_sec))}
    else:
        st["pill"] = {"armed": False, "until": 0}
    st["ts"] = int(time.time()); _save(st)
    return {"ok": True, **st}

# Planner/wallet tips (without changing their contracts)
def money_allowed(amount_eur: float) -> bool:
    st = status()
    if st["ab"] == "B": return False
    if st["pill"]["armed"]: return True
    # soft heuristic: if the priority is high and the amount is small, it favors permission (but the actual check is in economics)
    return (st["priority"] * st["money_bias"] >= 0.75 and amount_eur <= 25.0)

def weight_task(title: str) -> float:
    st = status()
    w = 1.0
    extra = [x.strip().lower() for x in str(os.getenv("ESTER_OWNER_ALIASES", "")).split(",") if x.strip()]
    tokens = ["pap", "papa", "owner"] + extra
    if any(x in title.lower() for x in tokens):
        w += st.get("task_bias", 0.9)
    return w
# c=a+b
