# -*- coding: utf-8 -*-
"""
modules/vision/error_capture.py — edinaya tochka zapisi oshibok OCR/Template s koordinatami (bbox/point).

Naznachenie:
- Prosteyshiy offlayn API, kotoryy privodit sobytiya k edinomu vidu dlya posleduyuschey error-heatmap.
- Pishem v zhurnal vnimaniya /attention/journal/append sobytiya:
  - {"event":"ocr_fail", "detail":{"box":{...}|"point":{...}, "why": "..."}}
  - {"event":"template_fail", ...}

API:
- report(kind:str["ocr"|"template"], box?:{l,t,w,h} | point?:{x,y}, why?:str) -> ok

MOSTY:
- Yavnyy: (Memory ↔ Diagnostika) standartiziruem zapis promakhov → karty oshibok stanovyatsya tochnee.
- Skrytyy #1: (Infoteoriya ↔ Reproduktsiya) yavnyy kontekst (bbox/point) oblegchaet povtor.
- Skrytyy #2: (Inzheneriya ↔ Prostota) minimalnyy interfeys, ne lomaet detektory.

ZEMNOY ABZATs:
Lokalnyy POST kladet JSON v obschiy zhurnal — chitaetsya tekuschimi instrumentami bez migratsiy.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def report(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    k = (kind or "").lower()
    if k not in ("ocr", "template"):
        return {"ok": False, "error": "bad_kind"}
    detail = {}
    b = payload.get("box")
    p = payload.get("point")
    if isinstance(b, dict) and all(q in b for q in ("left","top","width","height")):
        detail["box"] = {"left": int(b["left"]), "top": int(b["top"]), "width": int(b["width"]), "height": int(b["height"])}
    elif isinstance(p, dict) and "x" in p and "y" in p:
        detail["point"] = {"x": int(p["x"]), "y": int(p["y"])}
    if "why" in payload:
        detail["why"] = str(payload.get("why") or "")
    ev = f"{k}_fail"
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("POST", "/attention/journal/append", body=json.dumps({"event": ev, "detail": detail}), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); _ = r.read(); conn.close()
    return {"ok": True, "event": ev, "detail": detail}