# -*- coding: utf-8 -*-
"""modules/vision/auto_template_labeler.py - avto-razmetka shablonov iz makrologov.

Vkhod:
- Syrye sobytiya makrorekordera (/macro/preview) i/ili vruchnuyu peredannye zapisi:
  { "screen_b64": "...", "click": {"x":..,"y":..}, "title": "..." }

Ideaya:
- Dlya kazhdogo klika/goryachey klavishi pytaemsya izvlech okrestnost (bbox ~ 120x48) vokrug tochki klika
  ili predpolagaemoy pozitsii vidzheta (esli est box v zhurnale) - kak “kandidat shablona”.
- Formiruem plan shablonov: [{name, bbox:{l,t,w,h}, threshold, lang, note}], bez zapisi v triggery.

API:
- ingest(samples) -> add syrye primery (v pamyati)
- suggest(opts) -> build plan ({threshold_base, win=okno okrestnosti})
- export() -> return i ochistit ochered

MOSTY:
- Yavnyy: (Memory ↔ Videnie) “what nazhimali” → “what iskat.”
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) edinye parameter threshold/lang.
- Skrytyy #2: (Inzheneriya ↔ UX) vydaem plan bez pobochnykh effektov.

ZEMNOY ABZATs:
Offlayn: my ne vyrezaem PNG (t.k. bez PIL), a sokhranyaem bbox/metadannye dlya vneshnego izvlecheniya; skleyka - na suschestvuyuschikh /desktop/rpa/screen + downstream.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_buf: List[Dict[str, Any]] = []

def ingest(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    for s in samples or []:
        if isinstance(s, dict):
            _buf.append(s)
    return {"ok": True, "count": len(_buf)}

def suggest(opts: Dict[str, Any]) -> Dict[str, Any]:
    win_w = int(opts.get("win_w", 120)); win_h = int(opts.get("win_h", 48))
    thr   = float(opts.get("threshold_base", 0.82))
    lang  = str(opts.get("lang", "eng+rus"))
    plan = []
    for i, s in enumerate(_buf):
        pt = s.get("click") or {}
        x, y = int(pt.get("x",0)), int(pt.get("y",0))
        l, t = max(0, x - win_w//2), max(0, y - win_h//2)
        plan.append({
            "index": i,
            "name": s.get("title") or f"template_{i}",
            "bbox": {"left": l, "top": t, "width": win_w, "height": win_h},
            "threshold": thr,
            "lang": lang,
            "note": "candidate from macro click"
        })
    return {"ok": True, "count": len(plan), "plan": plan}

def export() -> Dict[str, Any]:
    global _buf
    out = list(_buf)
    _buf = []
    return {"ok": True, "exported": out}