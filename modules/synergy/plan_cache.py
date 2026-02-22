# -*- coding: utf-8 -*-
"""
modules/synergy/plan_cache.py — TTL-kesh prigodnostey i idempotentnykh planov.

MOSTY:
- (Yavnyy) Keshiruet scores agentov na 1–5 minut (ENV SYNERGY_SCORES_TTL_SEC) i plany po request_id (ENV SYNERGY_IDEMP_TTL_SEC).
- (Skrytyy #1) Invalidatsiya po updated_at agenta: esli agent menyalsya — prigodnosti pereschitayutsya.
- (Skrytyy #2) Potokobezopasnyy RLock, bez vneshnikh zavisimostey.

ZEMNOY ABZATs:
Snizhaet nagruzku i «drebezg»: ne schitaem odno i to zhe po sto raz, a povtornye zaprosy s odnim request_id vozvraschayut tot zhe plan.

# c=a+b
"""
from __future__ import annotations
import os, time, threading
from typing import Any, Dict, Optional, Tuple, Callable
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class PlanCache:
    def __init__(self):
        self._scores: Dict[str, Tuple[float, float, Dict[str, float]]] = {}  # agent_id -> (updated_at, expires, scores)
        self._plans: Dict[str, Tuple[float, Dict[str, Any]]] = {}            # request_id -> (expires, plan)
        self._lock = threading.RLock()

    def _ttl_scores(self) -> float:
        return float(os.getenv("SYNERGY_SCORES_TTL_SEC", "180") or 180.0)

    def _ttl_plans(self) -> float:
        return float(os.getenv("SYNERGY_IDEMP_TTL_SEC", "600") or 600.0)

    def get_scores(self, agent_id: str, updated_at: float, compute: Callable[[], Dict[str, float]]) -> Dict[str, float]:
        now = time.monotonic()
        with self._lock:
            rec = self._scores.get(agent_id)
            if rec:
                upd_at, exp, val = rec
                if upd_at == updated_at and exp > now:
                    return dict(val)
            val = compute()
            self._scores[agent_id] = (updated_at, now + self._ttl_scores(), dict(val))
            return dict(val)

    def get_plan(self, request_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not request_id:
            return None
        now = time.monotonic()
        with self._lock:
            rec = self._plans.get(request_id)
            if not rec:
                return None
            exp, plan = rec
            if exp < now:
                del self._plans[request_id]
                return None
            return plan

    def put_plan(self, request_id: Optional[str], plan: Dict[str, Any]) -> None:
        if not request_id:
            return
        with self._lock:
            self._plans[request_id] = (time.monotonic() + self._ttl_plans(), dict(plan))

CACHE = PlanCache()