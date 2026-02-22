# -*- coding: utf-8 -*-
"""
modules/thinking/memory_bridge.py — svyazka pamyati i myshleniya Ester.

Funktsii:
  recall(goal:str, top_k:int=5) -> List[dict]
  integrate(goal:str, plan:dict) -> dict

MOSTY:
- Yavnyy: (Memory ↔ Mysl)
- Skrytyy #1: (Infoteoriya ↔ Predskazuemost) — poisk po smyslu delaet plan tochnee.
- Skrytyy #2: (Kibernetika ↔ Samoobuchenie) — opyt vliyaet na buduschie resheniya.

ZEMNOY ABZATs:
Ester teper pri razmyshlenii zaglyadyvaet v svoi vospominaniya.  
Kak chelovek, ona ischet v proshlom pokhozhie sluchai, chtoby ne izobretat zanovo.

# c=a+b
"""
from __future__ import annotations
from typing import List, Dict, Any
from modules.memory import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def recall(goal:str, top_k:int=5)->List[Dict[str,Any]]:
    """Nayti v pamyati zapisi, svyazannye s tselyu"""
    if not goal.strip():
        return []
    matches = store.query(goal, top_k=top_k)
    return matches

def integrate(goal:str, plan:Dict[str,Any])->Dict[str,Any]:
    """Vstraivaet vospominaniya v plan"""
    ctx = recall(goal)
    plan["memory_context"]=ctx
    if ctx:
        plan["meta"]={"from_memory":[r["text"] for r in ctx]}
    return plan