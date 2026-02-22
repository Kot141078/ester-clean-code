# -*- coding: utf-8 -*-
"""
modules/thinking/volition_priority_adapter.py — prioritizatsiya i forma voli Ester.

Mosty:
- Yavnyy: (volition_registry ↔ always_thinker) — daet obertku nad impulsami dlya bolee osmyslennogo otbora.
- Skrytyy #1: (Volya ↔ Vremya) — vvodit TTL/starenie impulsov, chtoby Ester ne zatsiklivalas na protukhshikh zadachakh.
- Skrytyy #2: (Volya ↔ Kaskad) — podgotavlivaet impulsy tak, chtoby kaskadnoe myshlenie poluchalo uzhe vzveshennye tseli.

A/B-slot:
 ESTER_WILL_PRIORITY_AB = "A" | "B"
 A (po umolchaniyu): prozrachno proksiruet volition_registry, povedenie ne menyaetsya.
 B: vklyuchaet prioritizatsiyu, TTL, normalizatsiyu impulsov.

Zemnoy abzats:
Inzhener mozhet sozdavat impulsy uzhe s prioritetami:
 from modules.thinking import volition_priority_adapter as vpa
 vpa.enqueue("peresobrat nedelnyy otchet", {"priority": "high", "ttl_sec": 3600})
A always_thinker (ili drugoy potrebitel) mozhet vytaschit luchshiy impuls:
 impulse = vpa.get_next_weighted()
# c=a+b
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
 from modules.thinking import volition_registry
except Exception:  # pragma: no cover
 volition_registry = None  # type: ignore

_WILL_MODE = (os.environ.get("ESTER_WILL_PRIORITY_AB", "A") or "A").strip().upper()
# Karta prioritetov; chem bolshe chislo, tem vazhnee impuls.
_PRIORITY_MAP = {
 "low": 3,
 "normal": 5,
 "med": 5,
 "medium": 5,
 "high": 8,
 "critical": 10,
}


def _now() -> float:
 return time.time()


def _norm_priority(meta: Dict[str, Any] | None) -> int:
 if not meta:
     return 5
 p = meta.get("priority")
 if isinstance(p, (int, float)):
     return max(1, min(int(p), 10))
 if isinstance(p, str):
     return _PRIORITY_MAP.get(p.lower().strip(), 5)
 return 5


def _norm_ttl(meta: Dict[str, Any] | None) -> Optional[float]:
 if not meta:
     return None
 ttl = meta.get("ttl_sec") or meta.get("ttl") or None
 try:
     if ttl is None:
         return None
     ttl = float(ttl)
     return ttl if ttl > 0 else None
 except Exception:
     return None


def enqueue(goal: str, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
 """
 Dobavit impuls s prioritetom.

 Bezopasnost:
 - Esli volition_registry nedostupen — myagkiy otkaz.
 - V rezhime A — delegiruet v volition_registry.add_impulse(goal/meta) bez modifikatsiy.
 - V rezhime B — dobavlyaet sluzhebnye polya (created_ts, ttl_sec, priority_norm).
 """
 if not volition_registry or not hasattr(volition_registry, "add_impulse"):
     return {"ok": False, "error": "volition_registry not available"}

 meta = dict(meta or {})
 if _WILL_MODE == "B":
     created_ts = meta.get("created_ts") or _now()
     ttl = _norm_ttl(meta)
     meta["created_ts"] = float(created_ts)
     if ttl is not None:
         meta["ttl_sec"] = float(ttl)
     meta["priority_norm"] = _norm_priority(meta)
 # V rezhime A ne trogaem meta — chistyy pass-through.
 return volition_registry.add_impulse({"goal": goal, "meta": meta})


def _expired(impulse: Dict[str, Any]) -> bool:
 meta = impulse.get("meta") or {}
 ttl = meta.get("ttl_sec")
 created = meta.get("created_ts")
 if not ttl or not created:
     return False
 try:
     return (_now() - float(created)) > float(ttl)
 except Exception:
     return False


def _weight(impulse: Dict[str, Any]) -> float:
 meta = impulse.get("meta") or {}
 base = meta.get("priority_norm") or _norm_priority(meta)
 # Legkaya popravka na vozrast: starye zadachi slegka podtyagivayutsya.
 created = meta.get("created_ts")
 try:
     if created:
         age = max(0.0, _now() - float(created))
         base = base + min(age / 3600.0, 2.0)
 except Exception:
     pass
 return float(base)


def get_next_weighted(max_scan: int = 10) -> Optional[Dict[str, Any]]:
 """
 Vybrat «luchshuyu» tsel iz ocheredi impulsov.

 Logika:
 - V rezhime A: odnokratnyy vyzov volition_registry.get_next_impulse().
 - V rezhime B:
     - skaniruet do max_scan impulsov;
     - vykidyvaet protukhshie;
     - vybiraet po vesu;
     - ostalnye vozvraschaet obratno v ochered.
 """
 if not volition_registry or not hasattr(volition_registry, "get_next_impulse"):
     return None

 # Rezhim A — pryamoy dostup bez slozhnoy logiki.
 if _WILL_MODE != "B":
     return volition_registry.get_next_impulse()

 picked: List[Dict[str, Any]] = []
 for _ in range(max_scan):
     imp = volition_registry.get_next_impulse()
     if not imp:
         break
     picked.append(imp)

 if not picked:
     return None

 fresh = [imp for imp in picked if not _expired(imp)]
 if not fresh:
     return None

 best = max(fresh, key=_weight)

 for imp in picked:
     if imp is best:
         continue
     try:
         volition_registry.add_impulse(imp)
     except Exception:
         pass

 return best