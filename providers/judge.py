# -*- coding: utf-8 -*-
"""
JudgeProvider — sintez «luchshego» otveta (evristika poverkh local+cloud).
Metod: generate(prompt, temperature) -> str
"""
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
        # Evristicheskiy «dzhadzh»: vybiraem bolee informativnyy (dlina kak proksi)
# return a if len(a) >= len(b) else b