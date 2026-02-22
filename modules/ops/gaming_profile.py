# -*- coding: utf-8 -*-
"""
modules/ops/gaming_profile.py — «igrovye profili» tempa deystviy i dzhittera.

Profile opredelyaet:
- CPS/TPS: ogranichenie klikov/simvolov v sekundu
- delay_ms: bazovaya zaderzhka mezhdu shagami
- jitter: sluchaynyy shum po vremeni/koordinatam
- cursor_curve: 'linear'|'ease_in'|'ease_out'|'ease_in_out'

MOSTY:
- Yavnyy: (Volya ↔ Motorika) perevodit plan shagov v «chelovechnyy» ritm.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) determinirovannye ramki skorosti → menshe «banopodobnogo» povedeniya.
- Skrytyy #2: (Anatomiya ↔ Inzheneriya) mikrodrozh i krivye dvizheniya imitiruyut realnuyu ruku i glaz-ruku.

ZEMNOY ABZATs:
Pomogaet «igrat vmeste»: Ester ne spamit klikami, vyderzhivaet temp, slegka shumit koordinaty i dvigaet kursor plavno.
Vse parametry oflayn i nastraivaemye.

# c=a+b
"""
from __future__ import annotations
import time, math, random
from typing import Dict, Any, Iterable, Iterator
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PROFILES: Dict[str, Dict[str, Any]] = {
    "human_slow": {"cps": 3, "tps": 6, "delay_ms": 220, "jitter_px": 1, "jitter_ms": 25, "cursor_curve": "ease_in_out"},
    "human_norm": {"cps": 5, "tps": 9, "delay_ms": 160, "jitter_px": 2, "jitter_ms": 20, "cursor_curve": "ease_out"},
    "human_fast": {"cps": 8, "tps": 12, "delay_ms": 110, "jitter_px": 3, "jitter_ms": 15, "cursor_curve": "ease_out"},
}

def _sleep_ms(ms: int) -> None:
    time.sleep(max(0.0, ms/1000.0))

def _curve(t: float, kind: str) -> float:
    t = max(0.0, min(1.0, t))
    if kind == "ease_in":
        return t*t
    if kind == "ease_out":
        return 1.0 - (1.0 - t)*(1.0 - t)
    if kind == "ease_in_out":
        return 0.5*(1 - math.cos(math.pi*t))
    return t

def lerp(a: float, b: float, t: float) -> float:
    return a + (b-a)*t

def move_path(x0: int, y0: int, x1: int, y1: int, steps: int, curve: str) -> Iterable[Dict[str,int]]:
    for i in range(steps+1):
        t = _curve(i/float(steps), curve)
        yield {"x": int(lerp(x0, x1, t)), "y": int(lerp(y0, y1, t))}

def apply_jitter(x: int, y: int, px: int) -> tuple[int,int]:
    if px <= 0: return x,y
    return x + random.randint(-px, px), y + random.randint(-px, px)

def pace_constraints(profile: str) -> Dict[str, Any]:
    return PROFILES.get(profile, PROFILES["human_norm"])