# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def memory_manage_skill(action: str, text: str | None = None, record_id: str | None = None, top_k: int = 5) -> Dict[str, Any]:
    """Memory management: add/query/forget/static."""
    action = (action or "").strip().lower()
    try:
        from modules.memory import store  # type: ignore
    except Exception as e:
        return {"status": "error", "error": f"memory_store_unavailable:{e}"}

    if action == "add":
        if not text:
            return {"status": "error", "error": "text required for add"}
        rec = memory_add("fact", text, meta={"source": "skill_memory"})  # type: ignore
        return {"status": "ok", "record": rec}

    if action == "query":
        if not text:
            return {"status": "error", "error": "text required for query"}
        res = store.query(text, top_k=int(top_k or 5))  # type: ignore
        return {"status": "ok", "results": res}

    if action == "forget":
        if not record_id:
            return {"status": "error", "error": "record_id required for forget"}
        ok = store.forget(record_id)  # type: ignore
        return {"status": "ok", "deleted": bool(ok)}

    if action == "stats":
        return {"status": "ok", "stats": store.stats()}  # type: ignore

    return {"status": "error", "error": "unknown action"}