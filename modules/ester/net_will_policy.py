"""Ester Net Will Policy Adapter

Name:
- Safe A/B-layer dlya setevogo mosta.
- Chitaet ENV, chtoby reshit: mozhet li Ester ispolzovat vneshniy poisk sama.
- Yavnyy most mezhdu voley (will), setyu (net) i konfigom (ENV).

Invariance:
- Nikakikh setevykh vyzovov zdes.
- Just read ENV.
- Esli flagi ne vklyucheny, schitaetsya, chto setevoy poisk dlya Ester zapreschen.

Zemnoy abzats:
Kak v inzhenernoy sisteme pitaniya: etot modul - eto rubilnik i predokhranitel
mezhdu istochnikom (internet) i potrebitelem (Ester). Poka rubilnik v polozhenii A,
liniya obestochena; rezhim B vklyuchaet pitanie cherez kontroliruemyy avtomat."""

from __future__ import annotations

import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on", "b")


def get_net_will_config() -> Dict[str, Any]:
    """Vozvraschaet svodnuyu politiku setevogo mosta dlya verkhnego sloya.

    Klyuchi:
    - mode: A|B|AB|OFF
    - enabled: vklyuchen li most v printsipe
    - ester_allowed: mozhet li Ester vystupat istochnikom (source="ester")
    - log_all: logirovat li vse zaprosy kak osoznannye sobytiya
    - safe_defaults: description defoltnogo povedeniya dlya UI/diagnostiki"""
    raw_mode = (os.getenv("ESTER_NET_SEARCH_AB", "A") or "A").strip().upper()
    if raw_mode not in {"A", "B", "AB", "OFF"}:
        raw_mode = "A"

    ester_allowed = _bool_env("ESTER_NET_ALLOW_ESTER", False)
    log_all = _bool_env("ESTER_NET_LOG_ALL", True)

    enabled = raw_mode in {"B", "AB"} and ester_allowed

    return {
        "mode": raw_mode,
        "enabled": bool(enabled),
        "ester_allowed": bool(ester_allowed),
        "log_all": bool(log_all),
        "safe_defaults": {
            "no_hidden_daemons": True,
            "no_self_mod_without_consent": True,
            "network_only_via_will": True,
        },
    }