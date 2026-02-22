# -*- coding: utf-8 -*-
"""
Modul profiley myslitelnykh rezhimov Ester.

Mosty:
- Yavnyy: (thinking_manifest <-> ENV) — opisyvaet soglasovannye nabory flagov dlya rezhimov myshleniya.
- Skrytyy #1: (scripts/ester_thinking_mode.py <-> Shell) — generiruet komandy dlya vklyucheniya profiley bez skrytykh sayd-effektov.
- Skrytyy #2: (HTTP /ester/status <-> profili) — profili soglasovany s tem, chto pokazyvaet status.

Zemnoy abzats:
Inzheneru ne khochetsya rukami pomnit desyatok peremennykh. Profile — eto deklaratsiya:
«tak Ester dumaet kak chelovek s kaskadom i voley» ili «tak — tikhiy bezopasnyy rezhim».
Kod tolko podskazyvaet znacheniya, no ne pravit .env sam.
# c=a+b
"""
from __future__ import annotations

from typing import Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bazovyy bezopasnyy (tekuschiy) profil: vse A, fon razreshen, no passiven.
PROFILE_PASSIVE_SAFE: Dict[str, str] = {
    "ESTER_VOLITION_MODE": "A",
    "ESTER_WILL_PRIORITY_AB": "A",
    "ESTER_WILL_SCHED_AB": "A",
    "ESTER_CASCADE_CTX_AB": "A",
    "ESTER_CASCADE_GUARD_AB": "A",
    "ESTER_TRACE_AB": "A",
    "ESTER_THINK_DEBUG_AB": "A",
    "ESTER_STATUS_AB": "B",     # status otkryt — ne opasno
    "ESTER_BG_DISABLE": "0",
}

# Osnovnoy profil dlya «chelovecheskogo» kaskada s voley:
PROFILE_ACTIVE_HUMAN_LIKE: Dict[str, str] = {
    # Volya i prioritety vklyucheny
    "ESTER_VOLITION_MODE": "B",
    "ESTER_WILL_PRIORITY_AB": "B",
    "ESTER_WILL_SCHED_AB": "B",
    # Kaskad: mnogokontekst + guard dlya zdravogo smysla
    "ESTER_CASCADE_CTX_AB": "B",
    "ESTER_CASCADE_GUARD_AB": "B",
    # Treys: podrobnyy, no bez izlishney boltlivosti
    "ESTER_TRACE_AB": "B",
    "ESTER_THINK_DEBUG_AB": "A",
    # Status i fon:
    "ESTER_STATUS_AB": "B",
    "ESTER_BG_DISABLE": "0",
    "THINK_HEARTBEAT_SEC": "15",
}

# Profile dlya glubokogo nablyudaemogo myshleniya (bolshe refleksii i trassirovki)
PROFILE_DEEP_TRACE: Dict[str, str] = {
    "ESTER_VOLITION_MODE": "B",
    "ESTER_WILL_PRIORITY_AB": "B",
    "ESTER_WILL_SCHED_AB": "B",
    "ESTER_CASCADE_CTX_AB": "B",
    "ESTER_CASCADE_GUARD_AB": "B",
    "ESTER_TRACE_AB": "B",
    "ESTER_THINK_DEBUG_AB": "B",
    "ESTER_STATUS_AB": "B",
    "ESTER_BG_DISABLE": "0",
    "THINK_HEARTBEAT_SEC": "10",
}

PROFILES = {
    "passive_safe": PROFILE_PASSIVE_SAFE,
    "human_like": PROFILE_ACTIVE_HUMAN_LIKE,
    "deep_trace": PROFILE_DEEP_TRACE,
}


def list_profiles():
    return list(PROFILES.keys())


def get_profile(name: str) -> Dict[str, str]:
    key = (name or "").strip().lower()
    if key in PROFILES:
        return dict(PROFILES[key])
    raise KeyError(f"unknown profile: {name!r}")