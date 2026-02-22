# -*- coding: utf-8 -*-
"""
modules/ester/thinking_trace_adapter.py  (hotfix)

Ispravlenie:
- ispolzuem isinstance(..., dict), a ne typing.Dict.

Ostalnoe povedenie sovpadaet s iskhodnoy versiey.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_LOCK = threading.Lock()

_STATS: Dict[str, Any] = {
    "since": time.time(),
    "total": 0,
    "with_reflect": 0,
    "with_recall": 0,
    "depth_sum": 0,
    "depth_min": None,
    "depth_max": None,
}


def _mode() -> str:
    v = os.getenv("ESTER_THINK_TRACE_AB", "A") or "A"
    return v.strip().upper()


def is_enabled() -> bool:
    return _mode() in ("B", "AB", "ON")


def _upd_depth(depth: int) -> None:
    if depth <= 0:
        return
    with _LOCK:
        _STATS["depth_sum"] += depth
        if _STATS["depth_min"] is None or depth < _STATS["depth_min"]:
            _STATS["depth_min"] = depth
        if _STATS["depth_max"] is None or depth > _STATS["depth_max"]:
            _STATS["depth_max"] = depth


def record(request_payload: Dict[str, Any], response_json: Dict[str, Any]) -> None:
    """Neblokiruyuschaya zapis metrik. Oshibki ignoriruyutsya."""
    if not is_enabled():
        return
    try:
        has_reflect = False
        has_recall = False
        depth = 0

        if isinstance(response_json, dict):
            meta_val = response_json.get("meta") or response_json.get("stats") or {}
            if isinstance(meta_val, dict):
                depth = int(meta_val.get("depth", 0) or 0)
                has_reflect = bool(meta_val.get("reflect") or meta_val.get("has_reflect"))
                has_recall = bool(meta_val.get("recall") or meta_val.get("has_recall"))

            # popytka ugadat glubinu po shagam/trace
            if not depth:
                steps = response_json.get("steps")
                trace = response_json.get("trace")
                if isinstance(steps, list):
                    depth = len(steps)
                elif isinstance(trace, list):
                    depth = len(trace)

            # evristiki po refleksii
            if not has_reflect:
                for k in ("reflect", "reflection", "self_critique"):
                    if k in response_json:
                        has_reflect = True
                        break

            # evristiki po recall
            if not has_recall:
                for k in ("recall", "memory_hits", "evidence"):
                    if k in response_json:
                        has_recall = True
                        break

        with _LOCK:
            _STATS["total"] += 1
            if has_reflect:
                _STATS["with_reflect"] += 1
            if has_recall:
                _STATS["with_recall"] += 1
        if depth:
            _upd_depth(depth)
    except Exception:
        return


def get_stats() -> Dict[str, Any]:
    """Vozvraschaet stabilnyy snimok metrik. Nikogda ne brosaet isklyucheniya."""
    with _LOCK:
        total = _STATS["total"]
        depth_avg = 0.0
        if total and _STATS["depth_sum"]:
            depth_avg = float(_STATS["depth_sum"]) / float(total)
        return {
            "since": _STATS["since"],
            "mode": _mode(),
            "total": total,
            "with_reflect": _STATS["with_reflect"],
            "with_recall": _STATS["with_recall"],
            "depth_min": _STATS["depth_min"],
            "depth_max": _STATS["depth_max"],
            "depth_avg": depth_avg,
        }


__all__ = ["is_enabled", "record", "get_stats"]