# -*- coding: utf-8 -*-
"""
modules/triggers/mass_tuner.py — massovyy tyuning triggerov.

Funktsii:
- preview(opts) — vozvraschaet «plan pravok» bez primeneniya.
- apply(opts)   — vozvraschaet tot zhe plan (dlya prozrachnosti) i pytaetsya primenit pravki cherez REST
                 (esli v sisteme est /triggers/update; esli net — otdaem plan dlya ruchnogo primeneniya).

Parametry opts:
{
  "lang": "eng+rus",         # dlya vsekh OCR-triggerov
  "threshold": 0.80,         # dlya vsekh template-triggerov (esli nizhe — povysit)
  "scale_from_calibrate": true  # esli est /calibrate/status.scale -> dobavim pole "scale" triggeram
}

MOSTY:
- Yavnyy: (Diagnostika ↔ Deystvie) posle kart — paketnye pravki.
- Skrytyy #1: (Infoteoriya ↔ Reproduktsiya) edinoobraznye parametry snizhayut dispersiyu.
- Skrytyy #2: (Inzheneriya ↔ Prozrachnost) plan pravok otdelen ot primeneniya.

ZEMNOY ABZATs:
Tolko JSON i lokalnye ruchki. Nichego ne lomaem: esli obnovlenie nedostupno — vozvraschaem plan.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _plan(opts: Dict[str, Any]) -> Dict[str, Any]:
    trg = _get("/triggers/list")
    cases = []
    lang = opts.get("lang")
    thr  = float(opts.get("threshold", 0.8))
    scale_flag = bool(opts.get("scale_from_calibrate", True))
    scale = None
    if scale_flag:
        cal = _get("/calibrate/status")
        scale = cal.get("scale") or (cal.get("screen") or {}).get("scale") or None
    for i, t in enumerate(trg.get("triggers", [])):
        k = (t.get("kind") or "").lower()
        cond = dict(t.get("cond") or {})
        new = {}
        if k == "ocr_contains" and lang:
            if cond.get("lang") != lang:
                new["lang"] = lang
        if k == "template_match":
            th = float(cond.get("threshold", 0.78))
            if th < thr:
                new["threshold"] = thr
        if scale is not None:
            # dobavim informativnoe pole dlya klientskikh moduley
            if cond.get("scale") != scale:
                new["scale"] = scale
        if new:
            cases.append({"index": i, "kind": k, "new": new})
    return {"ok": True, "changes": cases}

def preview(opts: Dict[str, Any]) -> Dict[str, Any]:
    return _plan(opts)

def apply(opts: Dict[str, Any]) -> Dict[str, Any]:
    plan = _plan(opts)
    applied = []
    for ch in plan.get("changes", []):
        payload = {"index": ch["index"], "patch": ch["new"]}
        r = _post("/triggers/update", payload)  # esli takogo endpointa net — vyzov vernet ok:false/raw
        applied.append({"index": ch["index"], "ok": bool(r.get("ok")), "response": r})
    return {"ok": True, "plan": plan, "applied": applied}