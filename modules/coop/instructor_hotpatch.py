# -*- coding: utf-8 -*-
"""
modules/coop/instructor_hotpatch.py — bystryy tyuning triggerov vo vremya «rezhima instruktora».

Ideya:
- Na osnove vzveshennogo tyunera (modules.triggers.mass_tuner_weighted) gotovim plan patchey.
- V «rezhime instruktora» veduschiy vyzyvaet preview/apply → plan viden i mozhet byt primenen tochechno.
- Nikakikh fonovykh demonov: vyzov — deystvie — otchet.

API:
- preview(opts) -> plan (sm. mass_tuner_weighted.preview)
- apply(opts)   -> popytka primenit (sm. mass_tuner_weighted.apply)

MOSTY:
- Yavnyy: (Instruktor ↔ Kachestvo) snizhaet «goryachest» zon pryamo na uroke.
- Skrytyy #1: (Infoteoriya ↔ Upravlenie) prozrachnye parametry (radius/penalty/min_thr).
- Skrytyy #2: (Inzheneriya ↔ Bezopasnost) primenyaetsya tolko vruchnuyu i tolko lokalno.

ZEMNOY ABZATs:
Tonkaya prosloyka: prosto reeksport vyzovov tyunera, zhurnalom upravlyaet instruktorskaya sessiya.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
from modules.triggers.mass_tuner_weighted import preview as _prev, apply as _app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def preview(opts: Dict[str, Any]) -> Dict[str, Any]:
    return _prev(opts)

def apply(opts: Dict[str, Any]) -> Dict[str, Any]:
    return _app(opts)