# -*- coding: utf-8 -*-
"""
p2p.sync_client — minimalnye khelpery sinkhronizatsii.
# c=a+b
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def state_level(base_url: str | None = None, level: int = 0) -> Dict[str, Any]:
    # Fail-closed placeholder for offline mode; signature kept stable for callers.
    return {
        "ok": True,
        "state": "idle",
        "level": int(level or 0),
        "base_url": str(base_url or ""),
    }


def pull_by_ids(base_url_or_ids, ids: Optional[List[str]] = None) -> Dict[str, Any]:
    if ids is None and isinstance(base_url_or_ids, list):
        ids = base_url_or_ids
        base_url = None
    else:
        base_url = str(base_url_or_ids or "")
        ids = list(ids or [])
    return {
        "ok": True,
        "base_url": base_url,
        "items": [{"id": i, "found": False} for i in ids],
    }
