# -*- coding: utf-8 -*-
"""modules/thinking/proactive.py - proaktivnye triggery i avto-kaskady.

Funktsii:
  enable()/disable()/status()
  run_trigger(name, payload) — zapustit pravilo yavno
  load_rules() — zagruzka JSON-rules (user overrides)
  watcher_loop() — planirovschik: nablyudaet pamyat/dialogi i zapuskaet kaskady

Safety:
  - ENV ESTER_PROACTIVE_ENABLED (0/1)
  - Limit deystviy/hour (ESTER_PROACTIVE_MAX_ACTIONS)
  - Cooldown mezhdu kaskadami (ESTER_PROACTIVE_COOLDOWN_SEC)
  - Anti-repeat by klyuchu goal+rule (vremennyy cache)

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import os, time, json, threading
from modules.memory import store
from modules.memory.events import record_event
from modules.thinking import cascade
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

STATE = {
    "enabled": False,
    "last_trigger": None,
    "last_run_ts": 0,
    "actions_this_hour": 0,
    "running": False
}

_LOCK = threading.Lock()
_THR = None
_STOP = False
_CACHE: Dict[str,int] = {}  # goal_key -> ts

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store as _store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _env_on()->bool:
    return os.environ.get("ESTER_PROACTIVE_ENABLED","0")=="1"

def _limit()->int:
    try: return max(1, int(os.environ.get("ESTER_PROACTIVE_MAX_ACTIONS","5")))
    except: return 5

def _cooldown()->int:
    try: return max(30, int(os.environ.get("ESTER_PROACTIVE_COOLDOWN_SEC","300")))
    except: return 300

def _rules_path()->str:
    return os.environ.get("ESTER_PROACTIVE_RULES","rules/proactive_rules.json")

_DEFAULT_RULES = [
    # prostye i bezopasnye
    {"name":"weekly_plan", "match":{"contains":["plan na nedelyu","task list"]}, "goal":"Sformirovat nedelnyy plan", "action":"cascade"},
    {"name":"file_summary", "match":{"contains":["prochitan fayl","Prochitan fayl"]}, "goal":"Make a summary of the file you read", "action":"cascade"},
    {"name":"repeat_error", "match":{"contains":["act:","fail"]}, "goal":"Troubleshoot a recurring error", "action":"cascade"},
]

def load_rules()->List[Dict[str,Any]]:
    path=_rules_path()
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                obj=json.load(f)
                if isinstance(obj,list): return obj
        except Exception: pass
    return _DEFAULT_RULES

def _match_text(text:str, rule:Dict[str,Any])->bool:
    m=rule.get("match") or {}
    for s in m.get("contains",[]):
        if s.lower() in text.lower(): return True
    return False

def _hour_bucket()->int:
    return int(time.time()//3600)

def _budget_ok()->bool:
    with _LOCK:
        # reset the counter once per hour
        if STATE.get("_bucket")!=_hour_bucket():
            STATE["_bucket"]=_hour_bucket()
            STATE["actions_this_hour"]=0
        return STATE["actions_this_hour"] < _limit()

def _consume_budget():
    with _LOCK:
        STATE["actions_this_hour"]+=1

def run_trigger(name:str, payload:Dict[str,Any]|None=None)->Dict[str,Any]:
    payload=payload or {}
    goal=payload.get("goal") or f"vypolnit pravilo: {name}"
    key=f"{name}:{goal}"
    now=int(time.time())
    if key in _CACHE and now - _CACHE[key] < _cooldown():
        try:
            _mirror_background_event(
                f"[PROACTIVE_SKIP] {name} cooldown",
                "proactive",
                "skip",
            )
        except Exception:
            pass
        return {"ok":False,"reason":"cooldown"}
    if not _budget_ok():
        try:
            _mirror_background_event(
                f"[PROACTIVE_SKIP] {name} rate_limited",
                "proactive",
                "skip",
            )
        except Exception:
            pass
        return {"ok":False,"reason":"rate_limited"}
    _consume_budget()
    _CACHE[key]=now
    record_event("proactive","start",True,{"rule":name,"goal":goal})
    out=cascade.run_cascade(goal, payload.get("params") or {})
    STATE.update({"last_trigger":name,"last_run_ts":now})
    try:
        _mirror_background_event(
            f"[PROACTIVE_RUN] {name} goal={goal}",
            "proactive",
            "run",
        )
    except Exception:
        pass
    return {"ok":True,"result":out}

def _scan_memory_for_triggers(rules:List[Dict[str,Any]])->List[Dict[str,Any]]:
    # look only at the latest entries (last 200)
    items=sorted(store._MEM.values(), key=lambda r:r.get("ts",0), reverse=True)[:200]
    hits=[]
    for r in items:
        txt=r.get("text","")
        for rule in rules:
            if _match_text(txt, rule):
                hits.append({"rule":rule,"text":txt})
                break
    return hits

def watcher_loop():
    global _STOP
    if STATE["running"]: return
    STATE["running"]=True
    rules=load_rules()
    while not _STOP:
        if not _env_on():
            time.sleep(2); continue
        try:
            hits=_scan_memory_for_triggers(rules)
            for h in hits[:3]:  # v tik maksimum 3 srabatyvaniya
                run_trigger(h["rule"]["name"], {"goal":h["rule"]["goal"], "params":{}})
        except Exception:
            try:
                _mirror_background_event(
                    "[PROACTIVE_LOOP_ERROR]",
                    "proactive",
                    "loop_error",
                )
            except Exception:
                pass
            pass
        time.sleep(5)  # takt nablyudatelya
    STATE["running"]=False

def enable()->Dict[str,Any]:
    global _THR, _STOP
    if STATE["enabled"]:
        return {"ok":True,"enabled":True}
    if not _env_on():
        return {"ok":False,"error":"disabled_by_env"}
    _STOP=False
    _THR=threading.Thread(target=watcher_loop, name="ester-proactive", daemon=True)
    _THR.start()
    STATE["enabled"]=True
    try:
        _mirror_background_event(
            "[PROACTIVE_START]",
            "proactive",
            "start",
        )
    except Exception:
        pass
    return {"ok":True,"enabled":True}

def disable()->Dict[str,Any]:
    global _STOP
    _STOP=True
    STATE["enabled"]=False
    try:
        _mirror_background_event(
            "[PROACTIVE_STOP]",
            "proactive",
            "stop",
        )
    except Exception:
        pass
    return {"ok":True}

def status()->Dict[str,Any]:
    return {"ok":True, **STATE, "limit_per_hour":_limit(), "cooldown_sec":_cooldown()}