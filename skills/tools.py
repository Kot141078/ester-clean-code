# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def tools_skill(action: str = "summary") -> Dict[str, Any]:
    """
    Sistemnye instrumenty/diagnostika.
    """
    action = (action or "").strip().lower()
    if action == "summary":
        try:
            from modules.ops.summary import make_summary  # type: ignore
            return make_summary()  # type: ignore
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "unknown action"}