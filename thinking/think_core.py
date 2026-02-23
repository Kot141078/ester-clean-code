# -*- coding: utf-8 -*-
"""
thinking.think_core — tonkiy sloy sovmestimosti: THINKER + start=think
# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
import os, json
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# bezopasnye folbeki (sm. KOMPAT-008)
try:
    from modules.thinking.think_core import think as _think_impl, THINKER  # type: ignore
except Exception:
    def _think_impl(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        params = params or {}
        return {"ok": True, "goal": goal, "summary": "compat-think", "plan": {"steps":[]}, "exec": {"results": []}}
    class _T: 
        def think(self, goal, params=None): return _think_impl(goal, params)
        __call__ = think
        def __call__(self, goal, params=None): return _think_impl(goal, params)
    THINKER = _T()  # type: ignore

def think(goal: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return _think_impl(goal, params)

# alias expected by chat_routes
start = think
__all__ = ["THINKER", "think", "start"]