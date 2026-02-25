# -*- coding: utf-8 -*-
"""Validator (canon compatible): validate(payload) -> report
Checks the underlying fields, returns a structure with a summary."""
from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    issues = []
    if "query" in payload and not isinstance(payload.get("query"), str):
        issues.append({"field": "query", "msg": "must be string"})
    if "use_rag" in payload and not isinstance(payload.get("use_rag"), bool):
        issues.append({"field": "use_rag", "msg": "must be boolean"})
    ok = len(issues) == 0
    return {
        "ok": ok,
        "issues": issues,
        "size_bytes": len(str(payload).encode("utf-8")),
        "fields": sorted(list(payload.keys())),
    }
