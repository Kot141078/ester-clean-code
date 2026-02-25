# -*- coding: utf-8 -*-
"""modules/synergy/state_store.py - Potokobezopasnoe khranilische agentsov/komand.

Mosty:
- (Yavnyy) In-memory store s snapshotom sostoyaniya (agenty: lyudi/ustroystva; komandy i roli).
- (Skrytyy #1) Dvukhsloynyy indeks: po id i po tipam (human/device) — bystryy vyborki dlya orkestratora.
- (Skrytyy #2) Myagkaya konsistentnost: versii i atomarnye apdeyty pod lokom.

Zemnoy abzats:
Daet Ester “obschuyu dosku” dlya lyudey i mashin: kto dostupen, kakie navyki i kuda naznacheny.

# c=a+b"""
from __future__ import annotations
import threading
from typing import Dict, Any, Optional, List, Tuple
import time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class StateStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._v = 0
        self._agents: Dict[str, Dict[str, Any]] = {}   # id -> agent
        self._teams: Dict[str, Dict[str, Any]] = {}    # name -> team

    def upsert_agent(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        assert "id" in agent and "kind" in agent
        with self._lock:
            a = dict(agent)
            a.setdefault("meta", {})
            a["updated_at"] = time.time()
            self._agents[a["id"]] = a
            self._v += 1
            return a

    def list_agents(self, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            vals = list(self._agents.values())
            if kind:
                vals = [x for x in vals if x.get("kind") == kind]
            return [dict(x) for x in vals]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            a = self._agents.get(agent_id)
            return dict(a) if a else None

    def create_team(self, name: str, purpose: str, roles: List[str]) -> Dict[str, Any]:
        with self._lock:
            t = {"name": name, "purpose": purpose, "roles_needed": list(roles), "assigned": {}, "created_at": time.time()}
            self._teams[name] = t
            self._v += 1
            return dict(t)

    def get_team(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            t = self._teams.get(name)
            return dict(t) if t else None

    def assign_role(self, team: str, role: str, agent_id: str) -> None:
        with self._lock:
            t = self._teams[team]
            t.setdefault("assigned", {})[role] = agent_id
            self._v += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"v": self._v, "agents": [dict(x) for x in self._agents.values()], "teams": [dict(x) for x in self._teams.values()]}

STORE = StateStore()