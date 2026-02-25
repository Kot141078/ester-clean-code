# -*- coding: utf-8 -*-
"""CloudProvider - emulation of a cloud provider without external traffic.
Method: generate(prompt, temperature) -> page"""
from __future__ import annotations

import re
from typing import List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class CloudProvider:
    def models(self):
        return ["cloud/mock-3.5", "cloud/mock-4.1"]

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        p = (prompt or "").strip()
        # "cloud" answer is a little longer and more accurate
        p = re.sub(r"\s+", " ", p)
        tail = p[-220:]
# return f"Answer (cloud): ZZF0Z"