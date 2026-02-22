# -*- coding: utf-8 -*-
"""
modules/thinking/affect_reflection.py — prioritezatsiya refleksii s uchetom emotsiy i davnosti.

API:
  • score_item(item:dict) -> float  # 0..1
  • enqueue(item:dict) -> dict      # dobavlyaet v lokalnuyu ochered s prioritetom
  • pop(n:int=1) -> list[dict]      # beret n luchshikh

Signaly:
  • meta.affect: {valence[-1..1], arousal[0..1]}
  • recency: vozrast zapisi (sek)
  • importance: meta.importance (0..1)

Mosty:
- Yavnyy: (Memory ↔ Myshlenie) vazhnye i «emotsionalnye» zapisi refleksiruyutsya chasche i ranshe.
- Skrytyy #1: (Infoteoriya ↔ Planirovanie) prioritet uchityvaet davnost, izbegaya starvation.
- Skrytyy #2: (UX ↔ Obyasnimost) score vozvraschaetsya naruzhu — vidno, pochemu zapis vzyali pervoy.

Zemnoy abzats:
Eto «ochered s prioritetom»: silnye po smyslu/emotsiyam zapisi idut na obdumyvanie v pervuyu ochered.

# c=a+b
"""
from __future__ import annotations

import heapq
import time
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_ENABLE = True
_heap: List[Tuple[float, Dict[str, Any]]] = []  # (-score, item)

def _clip(x, lo, hi):
    return max(lo, min(hi, x))

def score_item(item: Dict[str, Any]) -> float:
    meta = dict(item.get("meta") or {})
    affect = dict(meta.get("affect") or {})
    val = float(affect.get("valence", 0.0))
    aro = float(affect.get("arousal", 0.0))
    imp = float(meta.get("importance", 0.5))
    ts = float(meta.get("ts", time.time()))
    age = time.time() - ts
    # Normalizatsiya
    val_n = 0.5 + 0.5 * _clip(val, -1.0, 1.0)     # [-1..1]→[0..1]
    aro_n = _clip(aro, 0.0, 1.0)
    imp_n = _clip(imp, 0.0, 1.0)
    recency = 1.0 / (1.0 + age / 3600.0)          # posledniy chas ≈ vysokiy ves
    score = 0.40 * aro_n + 0.25 * val_n + 0.25 * imp_n + 0.10 * recency
    return _clip(score, 0.0, 1.0)

def enqueue(item: Dict[str, Any]) -> Dict[str, Any]:
    s = score_item(item)
    heapq.heappush(_heap, (-float(s), dict(item, _score=float(s))))
    return {"ok": True, "score": float(s), "size": len(_heap)}

def pop(n: int = 1) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(max(1, n)):
        if not _heap:
            break
        s, it = heapq.heappop(_heap)
        out.append(it)
# return out