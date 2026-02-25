# -*- coding: utf-8 -*-
"""LocalProvider - fast local responses (heuristic generation).
Method: generate(prompt, temperature) -> page"""
from __future__ import annotations

import random
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_PREFIXES: List[str] = [
    "Ponyal. ",
    "Okey. ",
    "Korotko: ",
    "If it's on point:",
    "Summiruyu: ",
]


def _lead() -> str:
    return random.choice(_PREFIXES)


class LocalProvider:
    def models(self):
        return ["local/synth-v1"]

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        # Little variability and neat “summary”
        prompt = (prompt or "").strip()
        if not prompt:
            return "…"
        s = prompt.splitlines()
        head = s[0][:120]
        extra = "" if len(s) < 2 else " " + " ".join(x.strip() for x in s[1:3])
# return _lead() + head + extra