# -*- coding: utf-8 -*-
"""modules/thinking/profiles.py - presety profiley nagruzki dlya tsikla myshleniya.

MOSTY:
- Yavnyy: (Regulyatsiya ↔ Mysl) - tsentralizovannye profili v odnom meste.
- Skrytyy #1: (Inzheneriya sistem ↔ Kibernetika) - parameter dlya “gubernatora” (porogi CPU/GPU).
- Skrytyy #2: (UX/Operirovanie ↔ Stabilnost) — profile pod stsenarii: tikho/balans/maks.

ZEMNOY ABZATs:
Fayl daet prostye “tumblery moschnosti.” This is how rezhimy noutbuka: ekonomiya, sbalansirovannyy,
proizvoditelnyy. Tsikl myshleniya podstraivaet chastotu tikov i agressivnost, ne lomaya API.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROFILES: Dict[str, Dict[str, Any]] = {
    "quiet": {
        "tick_sleep": 0.60,
        "max_batch": 1,
        "idle_probe": True,
        "daily_tick": True,
        "governor": {
            "pause_when_busy": True,
            "cpu_high": 0.60,  # at >60% CNC and empty queue - lengthens pauses
            "cpu_low": 0.25,
            "gpu_high": 0.50,  # at >50% GPU and empty queue - lengthens pauses
            "gpu_low": 0.20,
            "sleep_add_hi": 0.50,
            "sleep_add_lo": 0.10,
        },
    },
    "balanced": {
        "tick_sleep": 0.25,
        "max_batch": 2,
        "idle_probe": True,
        "daily_tick": True,
        "governor": {
            "pause_when_busy": True,
            "cpu_high": 0.75,
            "cpu_low": 0.35,
            "gpu_high": 0.70,
            "gpu_low": 0.30,
            "sleep_add_hi": 0.30,
            "sleep_add_lo": 0.06,
        },
    },
    "max": {
        "tick_sleep": 0.05,
        "max_batch": 4,
        "idle_probe": False,   # maximum - less “background scent”
        "daily_tick": True,
        "governor": {
            "pause_when_busy": False,  # ne tormozim dazhe pri vysokoy zagruzke
            "cpu_high": 0.95,
            "cpu_low": 0.50,
            "gpu_high": 0.95,
            "gpu_low": 0.50,
            "sleep_add_hi": 0.00,
            "sleep_add_lo": 0.00,
        },
    },
}

DEFAULT_PROFILE = "balanced"

def get_preset(name: str | None):
    name = (name or "").strip().lower()
    return PROFILES.get(name, PROFILES[DEFAULT_PROFILE])

# c=a+b