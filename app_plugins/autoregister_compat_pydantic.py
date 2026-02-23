# -*- coding: utf-8 -*-
from __future__ import annotations
import os, warnings
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_PYDANTIC_AB", "B").upper()  # B=enable filter

def register(app=None):
    if _AB != "B":
        return
    try:
        import pydantic  # noqa
        warnings.filterwarnings(
            "ignore",
            message="Valid config keys have changed in V2",
            category=UserWarning,
            module=r"pydantic(\.|$)",
        )
    except Exception:
        pass
# c=a+b