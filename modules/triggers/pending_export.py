# -*- coding: utf-8 -*-
"""modules/triggers/pending_export.py - eksport "pending_add" iz plana v perenosimyy JSON.

Name:
- Prinimaem massiv “pending_add” (elementy plana bez index) i gotovim fayl-artefakt:
  [{name,bbox:{l,t,w,h},threshold,lang,note}] — bez zapisi v triggery.

API:
- normalize(items) -> validatsiya i normalizatsiya
- to_file(items, filename="pending_templates.json") -> bytes (soderzhimoe fayla) + metadannye

MOSTY:
- Yavnyy: (Diagnostika ↔ Operatsionka) yavno otdelyaem “kandidaty na dobavlenie” ot patchey.
- Skrytyy #1: (Infoteoriya ↔ Reproduktsiya) perenosimyy JSON dlya ruchnogo revyu.
- Skrytyy #2: (Inzheneriya ↔ Protsedury) ne lomaem kontrakty, tolko vneshniy artefakt.

ZEMNOY ABZATs:
Clean JSON, offline. Fayl otdaem kak bytes v HTTP-otvete (base64 v UI ne nuzhen).

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def normalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for it in items or []:
        bbox = it.get("bbox") or {}
        if not all(k in bbox for k in ("left","top","width","height")): 
            continue
        out.append({
            "name": it.get("name") or f"template_{len(out)}",
            "bbox": {
                "left": int(bbox["left"]), "top": int(bbox["top"]),
                "width": int(bbox["width"]), "height": int(bbox["height"])
            },
            "threshold": float(it.get("threshold", 0.85)),
            "lang": str(it.get("lang", "eng+rus")),
            "note": str(it.get("note", "pending_add export"))
        })
    return out

def to_file(items: List[Dict[str, Any]], filename: str = "") -> Dict[str, Any]:
    data = {"exported_at": int(time.time()), "kind": "pending_templates", "items": normalize(items)}
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    name = filename or f"pending_templates_{data['exported_at']}.json"
    return {"ok": True, "filename": name, "bytes": body, "count": len(data["items"])}