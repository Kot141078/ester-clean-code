# -*- coding: utf-8 -*-
"""
modules/test/auto_cases.py — avtogeneratsiya UI-testov iz zhurnalov i triggerov.

Istochniki:
- /attention/journal/list — sobytiya `trigger_fire`, `iplay_step`, `playlist_step` (berem ikh parametry).
- /triggers/list — aktivnye pravila (OCR/shablony).

Funktsii:
- mine() -> predlozhennye keysy [{name,kind,params,timeout_ms}]
- install() -> polozhit ikh v /ui/cases (cherez pryamye vyzovy funktsiy modulya)

MOSTY:
- Yavnyy: (Memory ↔ Kachestvo) deystviya/srabatyvaniya → testy.
- Skrytyy #1: (Infoteoriya ↔ Reproduktsiya) test vosproizvodit priznak, kotoryy uzhe rabotal.
- Skrytyy #2: (Kibernetika ↔ Evolyutsiya) s kazhdoy sessiey baza avtotestov bogateet.

ZEMNOY ABZATs:
Prostoy analiz JSON; nikakikh vneshnikh bibliotek. Taymaut po umolchaniyu 2 c.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import http.client, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("GET", path); r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse(); t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def mine(timeout_ms: int = 2000) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    # iz triggerov
    tr = _get("/triggers/list")
    for spec in tr.get("triggers", []):
        k = (spec.get("kind") or "").lower()
        if k == "ocr_contains":
            out.append({"name": f"OCR: {spec.get('cond',{}).get('text','')}", "kind": "ocr_contains", "params": {"text": spec.get("cond",{}).get("text",""), "lang": spec.get("cond",{}).get("lang","eng+rus")}, "timeout_ms": timeout_ms})
        elif k == "template_match":
            out.append({"name": "TEMPLATE", "kind": "template_match", "params": {"template_b64": spec.get("cond",{}).get("template_b64",""), "threshold": float(spec.get("cond",{}).get("threshold",0.78))}, "timeout_ms": timeout_ms})
    # iz zhurnala vnimaniya
    j = _get("/attention/journal/list?n=200")
    for itm in j.get("items", []):
        ev = itm.get("event")
        det = itm.get("detail") or {}
        if ev == "iplay_step" and det.get("ok"):
            # esli shag proshel — poprobuem OCR po titulu shaga
            ttl = str(det.get("title",""))
            if ttl:
                out.append({"name": f"Step OK: {ttl}", "kind":"ocr_contains", "params":{"text": ttl.split()[0], "lang":"eng+rus"}, "timeout_ms": timeout_ms})
        if ev == "trigger_fire":
            t = det.get("trig", {}).get("kind","")
            if t == "ocr_contains":
                out.append({"name":"Fire OCR", "kind":"ocr_contains", "params":{"text": det.get("trig",{}).get("cond",{}).get("text",""), "lang": det.get("trig",{}).get("cond",{}).get("lang","eng+rus")}, "timeout_ms": timeout_ms})
    # deduplikatsiya po (kind, params)
    uniq = []
    def _sig(x): return json.dumps([x.get("kind"), x.get("params")], sort_keys=True, ensure_ascii=False)
    for tc in out:
        if _sig(tc) not in uniq:
            uniq.append(_sig(tc))
    final = [tc for i, tc in enumerate(out) if _sig(tc) in uniq and not uniq.remove(_sig(tc))]
    return {"ok": True, "cases": final}

def install(timeout_ms: int = 2000) -> Dict[str, Any]:
    props = mine(timeout_ms=timeout_ms)
    from modules.test.ui_cases import add_case
    n = 0
    for cs in props.get("cases", []):
        add_case(cs); n += 1
    return {"ok": True, "installed": n}