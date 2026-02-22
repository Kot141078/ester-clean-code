# -*- coding: utf-8 -*-
"""
modules/agents/base_agent.py — obschiy karkas agentov deystviy (rasshirennyy M25).

Izmeneniya M25:
- _execute() teper pytaetsya vyzvat desktop_os_driver.execute(...) dlya agenta "desktop".
- Esli drayver vyklyuchen (ESTER_DD_ENABLED=0) ili ne primenim — ostaetsya simulyatsiya.
- Signatury/povedenie publichnykh metodov ne izmeneny.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
import os, time, threading, uuid

from modules.memory import store
from modules.memory.events import record_event
from modules.thinking import action_safety as AS
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

MAX_Q = int(os.environ.get("ESTER_AGENTS_MAX_QUEUE", "50"))
MODE = os.environ.get("ESTER_AGENTS_MODE", "A").upper()

class Action:
    def __init__(self, kind:str, meta:Dict[str,Any]|None=None):
        self.id = uuid.uuid4().hex[:10]
        self.kind = kind
        self.meta = meta or {}
        self.ts = int(time.time())
        self.status = "queued"  # queued|planned|denied|needs_consent|committed|done|error
        self.result: Dict[str,Any] = {}

class AgentBase:
    def __init__(self, name:str):
        self.name = name
        self.enabled = os.environ.get("ESTER_AGENTS_ENABLED","0")=="1"
        self.queue: List[Action] = []
        self.lock = threading.Lock()

    # --- ochered ---
    def enqueue(self, kind:str, meta:Dict[str,Any]|None=None)->Dict[str,Any]:
        with self.lock:
            if len(self.queue)>=MAX_Q:
                return {"ok":False,"error":"queue_full"}
            a=Action(kind, meta)
            self.queue.append(a)
            record_event("agent", f"{self.name}:enqueue", True, {"id":a.id,"kind":kind})
            return {"ok":True,"id":a.id}

    def list(self)->List[Dict[str,Any]]:
        with self.lock:
            return [{"id":a.id,"kind":a.kind,"status":a.status,"meta":a.meta,"result":a.result} for a in self.queue]

    # --- planirovanie i safety ---
    def plan(self, a:Action)->Tuple[List[Dict[str,Any]], Dict[str,Any]]:
        return [], {}

    def _safety(self, a:Action)->Dict[str,Any]:
        meta=a.meta.copy()
        meta.setdefault("steps", max(1, len(a.result.get("plan",[]))))
        return AS.decide(a.kind, meta)

    # --- dry-run/commit ---
    def dry_run(self, action_id:str)->Dict[str,Any]:
        a=self._get(action_id); 
        if not a: return {"ok":False,"error":"not_found"}
        plan, ctx = self.plan(a); a.result["plan"]=plan; a.result["ctx"]=ctx
        a.status="planned"
        dec=self._safety(a); a.result["safety"]=dec
        if dec.get("decision")=="deny": a.status="denied"
        elif dec.get("decision")=="needs_user_consent": a.status="needs_consent"
        record_event("agent", f"{self.name}:dry_run", True, {"id":a.id,"decision":dec.get("decision")})
        memory_add("event", f"agent:{self.name} dry-run {a.kind}", {"decision":dec,"plan_len":len(plan)})
        return {"ok":True,"id":a.id,"plan":plan,"decision":dec}

    def commit(self, action_id:str)->Dict[str,Any]:
        a=self._get(action_id); 
        if not a: return {"ok":False,"error":"not_found"}
        if a.status not in ("planned","needs_consent"):
            return {"ok":False,"error":"not_planned"}
        dec=a.result.get("safety") or self._safety(a)
        if dec.get("decision")=="deny":
            a.status="denied"; return {"ok":False,"error":"denied","decision":dec}
        # 'needs_user_consent' interpretiruem kak soglasie polzovatelya samim Commit
        ok, exec_res = self._execute(a)
        a.status="done" if ok else "error"
        a.result["exec"]=exec_res
        record_event("agent", f"{self.name}:commit", ok, {"id":a.id,"kind":a.kind})
        memory_add("event", f"agent:{self.name} commit {a.kind}", {"ok":ok,"exec":exec_res})
        return {"ok":ok,"id":a.id,"result":a.result}

    # --- ispolnenie ---
    def _execute(self, a:Action)->Tuple[bool,Dict[str,Any]]:
        """
        M25: esli eto desktop-agent i drayver vklyuchen — vypolnit cherez desktop_os_driver.execute
        inache — simulyatsiya.
        """
        try:
            if self.name=="desktop":
                from modules.agents import desktop_os_driver as DD
                plan=a.result.get("plan") or []
                # esli net plana — nechego delat
                if not plan:
                    return True, {"msg":"nothing to execute","steps":0}
                # dry_run ostavlyaem True, esli drayver ne vklyuchen v real
                enabled=os.environ.get("ESTER_DD_ENABLED","0")=="1"
                mode=os.environ.get("ESTER_DD_MODE","sandbox")
                dry = not (enabled and mode=="real")
                res=DD.execute(plan, dry_run=dry)
                return bool(res.get("ok",False)), {"driver":res}
        except Exception as e:
            return False, {"error":f"driver_error:{e}"}
        # fallback simulyatsiya
        return True, {"msg":"executed (simulated)", "steps": len(a.result.get("plan",[]))}

    # --- utility ---
    def _get(self, action_id:str)->Optional[Action]:
        with self.lock:
            return next((x for x in self.queue if x.id==action_id), None)