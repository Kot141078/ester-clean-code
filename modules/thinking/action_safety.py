# -*- coding: utf-8 -*-
"""
modules/thinking/action_safety.py — "remen bezopasnosti" pered deystviyami.

Funktsii:
  evaluate(action:str, meta:dict) -> dict  # otsenka riska/stoimosti + reshenie
  simulate(action:str, meta:dict, trials:int=50) -> dict  # bystraya Monte-Karlo otsenka
  commit(action:str, meta:dict) -> dict    # fiksatsiya raskhoda byudzheta (posle allow)
  config_get()/config_set()                # chtenie/izmenenie porogov
  budget_status()                          # ostatok byudzheta na sutki
  decide(action:str, meta:dict) -> dict    # evaluate + (po pravilam) auto-commit/require-consent

Naznachenie:
  — Pered zapuskom RPA/kaskada/payplayna otsenivaem "stoimost" i "risk", proveryaem
    pravila, dnevnoy byudzhet i trebuem li podtverzhdenie polzovatelya.

MOSTY:
- Yavnyy: (Mysl ↔ Deystvie) — vstavka safety-resheniya mezhdu planom i aktom.
- Skrytye:
  1) (Infoteoriya ↔ Ekonomiya) — byudzhet i udelnaya "stoimost" deystviy.
  2) (Kibernetika ↔ Nadezhnost) — simulyatsiya posledstviy + stop-krany.
  3) (Inzheneriya ↔ UX) — edinyy REST/UI, prozrachnye prichiny resheniya.

ZEMNOY ABZATs:
Inzhenerno — eto kalkulyator riska/stoimosti s prostym pravilom vybora.
Prakticheski — Ester perestaet "zhat na vse": ona snachala dumaet, skolko eto
stoit i naskolko riskovanno, i tolko potom deystvuet (ili prosit soglasie).

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import os, time, json, math, random
from modules.memory import store
from modules.memory.events import record_event
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Konfiguratsiya/byudzhet ---
_CFG = {
    "enabled": os.environ.get("ESTER_ACTION_SAFETY_ENABLED","1") == "1",
    "risk_tol": float(os.environ.get("ESTER_ACTION_SAFETY_RISK_TOL","0.35")),
    "cost_budget_daily": int(os.environ.get("ESTER_ACTION_SAFETY_COST_BUDGET","100")),
    "rules_path": os.environ.get("ESTER_ACTION_SAFETY_RULES","rules/action_safety_rules.json")
}
_STATE = {
    "bucket_day": int(time.time())//86400,
    "spent_today": 0
}

# --- Pravila (kastom + defolt) ---
_DEFAULT_RULES = [
    # action, base_cost, base_risk, need_consent?
    {"match": {"action": "install_software"}, "base_cost": 20, "base_risk": 0.25, "need_consent": True},
    {"match": {"action": "open_url"},         "base_cost": 1,  "base_risk": 0.05, "need_consent": False},
    {"match": {"action": "delete_files"},     "base_cost": 40, "base_risk": 0.60, "need_consent": True},
    {"match": {"action": "edit_config"},      "base_cost": 10, "base_risk": 0.30, "need_consent": True},
    {"match": {"action": "send_message"},     "base_cost": 2,  "base_risk": 0.10, "need_consent": False},
]

def _load_rules() -> List[Dict[str,Any]]:
    p = _CFG["rules_path"]
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f:
                obj=json.load(f)
                if isinstance(obj,list) and obj: return obj
        except Exception:
            pass
    return _DEFAULT_RULES

_RULES = _load_rules()

def config_get()->Dict[str,Any]:
    return {"ok": True, "config": _CFG, "rules_count": len(_RULES)}

def config_set(patch: Dict[str,Any])->Dict[str,Any]:
    if "risk_tol" in patch:
        _CFG["risk_tol"] = float(patch["risk_tol"])
    if "cost_budget_daily" in patch:
        _CFG["cost_budget_daily"] = int(patch["cost_budget_daily"])
    if "enabled" in patch:
        _CFG["enabled"] = bool(patch["enabled"])
    return {"ok": True, "config": _CFG}

def _reset_bucket_if_needed():
    d = int(time.time())//86400
    if d != _STATE["bucket_day"]:
        _STATE["bucket_day"] = d
        _STATE["spent_today"] = 0

def budget_status()->Dict[str,Any]:
    _reset_bucket_if_needed()
    return {"ok": True, "spent_today": _STATE["spent_today"], "budget_daily": _CFG["cost_budget_daily"]}

# --- Otsenka cost/risk ---
def _match_rule(action:str)->Dict[str,Any]:
    for r in _RULES:
        if r.get("match",{}).get("action")==action:
            return r
    return {}

def _meta_cost(meta:Dict[str,Any])->float:
    # bystrye evristiki: masshtab, chislo faylov/okon, glubina avtomatizatsii…
    scale = float(meta.get("scale", 1.0))
    files = int(meta.get("files", 0))
    steps = int(meta.get("steps", 1))
    return 1.0*scale + 0.1*files + 0.5*max(0,steps-1)

def _meta_risk(meta:Dict[str,Any])->float:
    # evristiki riska: privilegii, neobratimost, set, neizvestnyy vendor…
    priv = 0.2 if meta.get("requires_admin") else 0.0
    irreversible = 0.3 if meta.get("irreversible") else 0.0
    net = 0.1 if meta.get("network") else 0.0
    unknown = 0.2 if meta.get("unknown_vendor") else 0.0
    return priv + irreversible + net + unknown

def evaluate(action:str, meta:Dict[str,Any]|None=None)->Dict[str,Any]:
    meta = meta or {}
    _reset_bucket_if_needed()
    base = _match_rule(action)
    base_cost = float(base.get("base_cost", 5.0))
    base_risk = float(base.get("base_risk", 0.2))
    need_consent = bool(base.get("need_consent", False))
    cost = base_cost + _meta_cost(meta)
    risk = min(1.0, max(0.0, base_risk + _meta_risk(meta)))
    allow = (risk <= _CFG["risk_tol"]) and ((_STATE["spent_today"] + cost) <= _CFG["cost_budget_daily"])
    decision = "allow" if allow else ("needs_user_consent" if need_consent else "deny")
    out = {
        "ok": True, "action": action, "cost": round(cost,2), "risk": round(risk,2),
        "risk_tol": _CFG["risk_tol"], "budget_left": max(0, _CFG["cost_budget_daily"]-_STATE["spent_today"]),
        "needs_consent": need_consent, "decision": decision
    }
    return out

# --- Bystraya simulyatsiya iskhodov (Monte-Karlo) ---
def simulate(action:str, meta:Dict[str,Any]|None=None, trials:int=50)->Dict[str,Any]:
    meta = meta or {}
    ev = evaluate(action, meta)
    risk = float(ev["risk"])
    # veroyatnost "uspekha" kak 1 - risk (grubo, no operabelno)
    p_success = max(0.0, min(1.0, 1.0 - risk))
    succ=0; fail=0; near=0
    for _ in range(max(1,int(trials))):
        r = random.random()
        if r < p_success: succ+=1
        elif r < (p_success + (risk*0.3)): near+=1   # pochti uspeshno/chastichnyy rezultat
        else: fail+=1
    return {"ok": True, "action": action, "trials": trials, "p_success": round(p_success,2),
            "hist": {"success": succ, "near": near, "fail": fail}}

# --- Prinyatie resheniya i fiksatsiya ---
def commit(action:str, meta:Dict[str,Any]|None=None)->Dict[str,Any]:
    ev = evaluate(action, meta or {})
    if ev["decision"] == "deny":
        return {"ok": False, "error": "denied", **ev}
    # spisyvaem byudzhet
    _STATE["spent_today"] += float(ev["cost"])
    record_event("safety", "commit", True, {"action": action, "cost": ev["cost"], "risk": ev["risk"]})
    # sled v pamyat dlya trassirovki
    memory_add("event", f"safety:commit {action}", {"cost": ev["cost"], "risk": ev["risk"]})
    return {"ok": True, **ev}

def decide(action:str, meta:Dict[str,Any]|None=None)->Dict[str,Any]:
    ev = evaluate(action, meta or {})
    if not _CFG["enabled"]:
        ev["decision"] = "allow"
        return ev
    if ev["decision"] == "allow":
        return commit(action, meta)
    if ev["decision"] == "needs_user_consent":
        # fiksiruem zapros na soglasie (UI/chat mozhet podkhvatit)
        record_event("safety", "consent_required", True, {"action": action, "cost": ev["cost"], "risk": ev["risk"]})
        memory_add("event", f"safety:consent {action}", {"cost": ev["cost"], "risk": ev["risk"]})
        return ev
    # deny
    record_event("safety", "deny", False, {"action": action, "cost": ev["cost"], "risk": ev["risk"]})
    return ev