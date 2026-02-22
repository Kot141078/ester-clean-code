# -*- coding: utf-8 -*-
"""
modules/thinking/affect_reflect.py — prioritezatsiya refleksii po emotsiyam (affect-aware).

Mosty:
- Yavnyy: (Emotsii ↔ Refleksiya) zapisi s vysokim affektom poluchayut bolshiy ves dlya «short reflection».
- Skrytyy #1: (Memory ↔ Poisk) zabiraem poslednie zapisi cherez flashback/poisk.
- Skrytyy #2: (Volya ↔ Plan) vydaem spisok prioritetov i (opts.) initsiiruem refleksiyu.

Zemnoy abzats:
Eto kak «signal trevogi»: esli zapis goryachaya ili emotsionalnaya — snachala dumaem o ney.

# c=a+b
"""
from __future__ import annotations
import json, urllib.request
from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _http_json(url: str, body: Dict[str,Any]|None=None, timeout: int=20)->Dict[str,Any]:
    data = json.dumps(body or {}).encode("utf-8") if body is not None else None
    req  = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}) if body is not None else urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _flashback(limit: int=200)->List[Dict[str,Any]]:
    try:
        rep=_http_json(f"http://127.0.0.1:8000/mem/flashback?limit={limit}")
        if rep.get("ok"): return rep.get("items") or []
    except Exception:
        pass
    return []

def prioritize(limit: int=200, topk: int=20)->Dict[str,Any]:
    items=_flashback(limit)
    # ozhidaem polya meta.affect (0..1) ili meta.emotion.score; inache 0.0
    scored=[]
    for it in items:
        meta=it.get("meta") or {}
        aff=float(meta.get("affect", meta.get("emotion",{}).get("score",0.0)) or 0.0)
        pri=aff*0.7 + float(meta.get("importance",0.0))*0.3
        scored.append((pri, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    top=[x[1] for x in scored[:topk]]
    return {"ok": True, "top": top, "explain": {"scored": len(scored)}}
# c=a+b