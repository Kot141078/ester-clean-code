# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def web_search_skill(query: str, topk: int = 5) -> Dict[str, Any]:
    """
    Veb-poisk cherez modules.web_search.
    """
    q = (query or "").strip()
    if not q:
        return {"status": "error", "error": "query required"}
    try:
        from modules.web_search import search_web  # type: ignore
    except Exception as e:
        return {"status": "error", "error": f"web_search_unavailable:{e}"}
    items = search_web(q, topk=topk)
    return {"status": "ok", "items": items}