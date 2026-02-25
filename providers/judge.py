# -*- coding: utf-8 -*-
"""YudzheProvider - synthesis of the “best” answer (heuristics on top of local+cloud).
Method: generate(prompt, temperature) -> page"""
from __future__ import annotations

from .cloud import CloudProvider
from .local import LocalProvider
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class JudgeProvider:
    def __init__(self):
        self.local = LocalProvider()
        self.cloud = CloudProvider()

    def models(self):
        return ["judge/mixer-v1"]

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        a = self.local.generate(prompt, temperature=temperature)
        b = self.cloud.generate(prompt, temperature=temperature)
        # Heuristic “judge”: choose the more informative one (length as a proxy)
# return a if len(a) >= len(b) else b