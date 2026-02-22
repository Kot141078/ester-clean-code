# -*- coding: utf-8 -*-
"""
modules/policy/engine.py — sloy politik (RBAC + usloviya) poverkh Safety.

Naznachenie:
- Tsentralizovannye pravila «kto-chto-kogda-gde-pri kakikh usloviyakh».
- Komponovka s suschestvuyuschim Safety (M20): politika mozhet uzhestochit reshenie.
- Roli: user:*, machine:*, group:*. Resursy: agent/kind (naprimer, "agent:desktop/click").
- Usloviya: vremya, rezhimy (A/B), whitelist/real-mode, flazhki meta (requires_admin, steps), risk.

MOSTY:
- Yavnyy: (Safety ↔ Politika) — edinoe itogovoe reshenie dlya deystviya.
- Skrytyy #1: (Kibernetika ↔ Upravlenie) — yavnye pravila → predskazuemost.
- Skrytyy #2: (Infoteoriya ↔ Szhatie politiki) — korotkie deklaratsii → dlinnye stsenarii.

ZEMNOY ABZATs:
Inzhenerno — eto filtr-politika s rolyami i usloviyami. Prakticheski — mozhno strogo
zadat, komu i kogda razresheny kliki/ustanovki/vvod, i kak politika sshivaetsya s Safety.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import os, json, time
from datetime import datetime
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

POLICY_ENABLED = os.environ.get("ESTER_POLICY_ENABLED","1") == "1"
POLICY_MODE = os.environ.get("ESTER_POLICY_MODE","A").upper()  # A=advisory, B=strict
POLICY_PATH = os.environ.get("ESTER_POLICY_PATH","data/policy/policies.json")

# --------- zagruzka/sokhranenie ---------
def _ensure_default():
    if os.path.exists(POLICY_PATH): return
    os.makedirs(os.path.dirname(POLICY_PATH), exist_ok=True)
    default = {
      "ts": int(time.time()),
      "roles": {
        "user:default": {"inherits": [], "meta": {}},
        "machine:local": {"inherits": [], "meta": {}}
      },
      "rules": [
        # Primery:
        # Razreshaem bezopasnye operatsii rabochego stola v rezhime A (dry)
        {"id":"r1","subjects":["user:*"],"resource":"agent:desktop/*","effect":"allow","conditions":{"mode":["A"]}},
        # Kliki realnogo rezhima tolko s soglasiem
        {"id":"r2","subjects":["user:*"],"resource":"agent:desktop/click","effect":"needs_user_consent","conditions":{"real":["1"]}},
        # Ustanovka PO trebuet soglasiya i requires_admin=true
        {"id":"r3","subjects":["user:*"],"resource":"agent:installer/*","effect":"needs_user_consent","conditions":{"requires_admin":[True]}},
        # Zapret na >20 shagov v plane
        {"id":"r4","subjects":["user:*"],"resource":"agent:*/*","effect":"deny","conditions":{"steps_gt":20}}
      ],
      "order": ["r4","r3","r2","r1"]  # poryadok primeneniya (pervoe sovpadenie silnee)
    }
    with open(POLICY_PATH,"w",encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=2)

def _load()->Dict[str,Any]:
    _ensure_default()
    try:
        with open(POLICY_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"roles":{},"rules":[],"order":[]}

def _save(obj:Dict[str,Any])->Dict[str,Any]:
    obj["ts"]=int(time.time())
    os.makedirs(os.path.dirname(POLICY_PATH), exist_ok=True)
    with open(POLICY_PATH,"w",encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return {"ok":True,"path":POLICY_PATH}

# --------- utility ---------
def list_all()->Dict[str,Any]:
    return {"ok":True, **_load()}

def save_all(obj:Dict[str,Any])->Dict[str,Any]:
    return _save(obj)

def _match_resource(rule_res:str, res:str)->bool:
    # rule_res: "agent:desktop/*"  vs res: "agent:desktop/click"
    if rule_res.endswith("/*"):
        return res.startswith(rule_res[:-2])
    return rule_res == res or rule_res == "agent:*/*"

def _subject_ok(subject:str, allowed:List[str])->bool:
    # supports user:*, machine:*, group:*
    if "user:*" in allowed: return True
    return subject in allowed

def _cond_ok(conds:Dict[str,Any], ctx:Dict[str,Any])->bool:
    if not conds: return True
    # mode A/B
    if "mode" in conds and str(ctx.get("mode","A")) not in [str(x) for x in conds["mode"]]:
        return False
    # real mode (desktop driver)
    if "real" in conds:
        v = "1" if ctx.get("real_enabled") else "0"
        if v not in [str(x) for x in conds["real"]]:
            return False
    # requires_admin from meta
    if "requires_admin" in conds:
        if bool(ctx.get("requires_admin")) not in [bool(x) for x in conds["requires_admin"]]:
            return False
    # steps_gt
    if "steps_gt" in conds:
        if int(ctx.get("steps",0)) <= int(conds["steps_gt"]):
            return False
    # time window (HH:MM-HH:MM, lokalnoe)
    if "time_window" in conds:
        try:
            now = datetime.now().strftime("%H:%M")
            start, end = conds["time_window"].split("-")
            if not (start <= now <= end): return False
        except Exception:
            return False
    return True

def _compose(safety_decision:str, policy_effect:str)->str:
    """
    Komponovka Safety (allow/needs_user_consent/deny) i Policy (allow/needs_user_consent/deny).
    V strogom rezhime politika mozhet tolko uzhestochit reshenie.
    """
    # esli politika deny — vsegda deny
    if policy_effect=="deny":
        return "deny"
    # esli politika needs — minimum needs
    if policy_effect=="needs_user_consent":
        return "needs_user_consent"
    # policy allow:
    if POLICY_MODE=="A":
        # advisory: vozvraschaem Safety kak iskhodnik
        return safety_decision
    # strict: allow → ne myagche Safety
    return safety_decision

def evaluate(agent:str, kind:str, meta:Dict[str,Any], subject:str, safety_decision:str|None=None, ctx:Dict[str,Any]|None=None)->Dict[str,Any]:
    """
    Vozvraschaet itog: decision, matched_rule, compose(safety,policy).
    - agent: "desktop" | "installer" | "game" | ...
    - kind:  "open_app" | "click" | ...
    - subject: "user:default" | "machine:local" | ...
    - safety_decision: optsionalno — reshenie iz Safety (esli est).
    - ctx: {"mode":"A|B","real_enabled":bool,"requires_admin":bool,"steps":int}
    """
    if not POLICY_ENABLED:
        return {"ok":True,"decision": safety_decision or "allow", "policy":"disabled"}
    data=_load()
    res=f"agent:{agent}/{kind}"
    order=data.get("order") or [r.get("id") for r in data.get("rules",[])]
    rules={r.get("id"):r for r in data.get("rules",[])}
    matched=None; effect="allow"
    for rid in order:
        r = rules.get(rid); 
        if not r: continue
        if not _subject_ok(subject, r.get("subjects",[])): continue
        if not _match_resource(r.get("resource","agent:*/*"), res): continue
        if not _cond_ok(r.get("conditions",{}), ctx or {}): continue
        matched=r; effect=r.get("effect","allow"); break
    final=_compose(safety_decision or "allow", effect)
    return {"ok":True,"decision":final,"effect":effect,"matched_rule":matched, "safety":safety_decision or "allow", "mode":POLICY_MODE}

# Uproschennyy khelper dlya agentov/routov
def decide_with_policy(agent:str, kind:str, meta:Dict[str,Any], subject:str, safety_decision:str, ctx:Dict[str,Any])->Dict[str,Any]:
    return evaluate(agent, kind, meta, subject, safety_decision, ctx)