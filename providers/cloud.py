# -*- coding: utf-8 -*-
"""
CloudProvider — emulyatsiya oblachnogo provaydera bez vneshnego trafika.
Metod: generate(prompt, temperature) -> str
"""
from __future__ import annotations

import re
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class CloudProvider:
    def models(self):
        return ["cloud/mock-3.5", "cloud/mock-4.1"]

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        p = (prompt or "").strip()
        # «oblachnyy» otvet chut dlinnee i bolee akkuratnyy
        p = re.sub(r"\s+", " ", p)
        tail = p[-220:]
# return f"Otvet (cloud): {tail}"