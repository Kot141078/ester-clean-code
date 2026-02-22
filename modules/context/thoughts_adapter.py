# -*- coding: utf-8 -*-
"""
modules/context/thoughts_adapter.py — fiksatsiya vnutrennikh mysley i rassuzhdeniy.

Ispolzuetsya vnutri thinking.loop_full i agent_loop
dlya zapisi razmyshleniy, vyvodov i resheniy.

# c=a+b
"""
from modules.context.adapters import log_context
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def record_thought(goal: str, conclusion: str, success: bool = True) -> None:
    state = "uspeshno" if success else "s somneniyami"
    text = f"Razmyshlenie o '{goal}' zaversheno {state}: {conclusion}"
    log_context("thought", "dream", text, {"goal": goal, "success": success})