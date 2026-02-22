# -*- coding: utf-8 -*-
"""
modules/ester/status.py — svodnyy status rezhimov i kaskadnogo myshleniya Ester.

Mosty:
- Yavnyy: (ENV ↔ HTTP/CLI) — edinyy istochnik pravdy po rezhimam.
- Skrytyy #1: (thinking/volition ↔ orchestrator) — pokazyvaet, kakie kontury aktivny.
- Skrytyy #2: (trace/debug ↔ chelovek) — daet kratkiy chelovekochitaemyy itog.

Zemnoy abzats:
Inzheneru nuzhno ponyat, kak seychas dumaet Ester. Odin vyzov get_status()
vozvraschaet rezhimy kaskada, voli, guard, trace i debug.
# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _env_flag(name: str, default: str = "A") -> str:
    return (os.getenv(name, default) or default).strip().upper()


def get_status() -> Dict[str, Any]:
    """Vernut strukturirovannyy status klyuchevykh rezhimov Ester."""
    return {
        "volition": {
            "ESTER_VOLITION_MODE": _env_flag("ESTER_VOLITION_MODE", "A"),
            "ESTER_WILL_PRIORITY_AB": _env_flag("ESTER_WILL_PRIORITY_AB", "A"),
            "ESTER_WILL_SCHED_AB": _env_flag("ESTER_WILL_SCHED_AB", "A"),
        },
        "cascade": {
            "ESTER_CASCADE_CTX_AB": _env_flag("ESTER_CASCADE_CTX_AB", "A"),
            "ESTER_CASCADE_GUARD_AB": _env_flag("ESTER_CASCADE_GUARD_AB", "A"),
        },
        "trace": {
            "ESTER_TRACE_AB": _env_flag("ESTER_TRACE_AB", "A"),
            "ESTER_THINK_DEBUG_AB": _env_flag("ESTER_THINK_DEBUG_AB", "A"),
        },
        "background": {
            "ESTER_BG_DISABLE": (os.getenv("ESTER_BG_DISABLE", "0") or "0"),
            "THINK_HEARTBEAT_SEC": os.getenv("THINK_HEARTBEAT_SEC"),
        },
    }


def get_human_summary() -> str:
    """Chelovekochitaemoe rezyume rezhimov."""
    st = get_status()
    parts = []

    vm = st["volition"]["ESTER_VOLITION_MODE"]
    if vm == "B":
        parts.append("volya vklyuchena (impulsy prinimayutsya)")
    else:
        parts.append("volya v passivnom rezhime")

    if st["volition"]["ESTER_WILL_PRIORITY_AB"] == "B":
        parts.append("prioritety tseley uchityvayutsya")
    if st["volition"]["ESTER_WILL_SCHED_AB"] == "B":
        parts.append("planirovschik voli aktiven")

    if st["cascade"]["ESTER_CASCADE_CTX_AB"] == "B":
        parts.append("mnogokontekstnyy kaskad myshleniya vklyuchen")
    if st["cascade"]["ESTER_CASCADE_GUARD_AB"] == "B":
        parts.append("guard kaskada aktiven (ogranicheniya po shagam/chastote)")

    tr = st["trace"]["ESTER_TRACE_AB"]
    if tr == "B":
        parts.append("polnyy treys myshleniya vklyuchen")
    elif tr == "A":
        parts.append("kratkiy treys myshleniya vklyuchen pri nalichii adaptera")

    if st["trace"]["ESTER_THINK_DEBUG_AB"] == "B":
        parts.append("debug-marshruty /ester/thinking-debug/* razresheny")

    bg_dis = (st["background"]["ESTER_BG_DISABLE"] or "0").lower() in ("1", "true", "yes")
    if bg_dis:
        parts.append("fonovye moduli otklyucheny")
    else:
        hb = st["background"]["THINK_HEARTBEAT_SEC"] or "po umolchaniyu"
        parts.append(f"fonovye myslitelnye tsikly razresheny (interval {hb} sek)")

    return " ; ".join(parts)