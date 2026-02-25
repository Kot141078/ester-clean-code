# -*- coding: utf-8 -*-
"""modules/test/ui_cases.py - vizualnye test-keysy poverkh suschestvuyuschikh detektorov (OCR/shablony).

Spetsifikatsiya testa:
{
  "name": "Menu has 'Fayl'",
  "kind": "ocr_contains", # or template_match
  "params": {"text":"Fayl","lang":"rus+eng"},
  "timeout_ms": 2000
}

API:
- add_case(case), list_cases(), clear_cases()
- run_all() -> {"total":N,"passed":M,"failed":K,"results":[...]}
- export_json() -> JSON resultata poslednego progona

MOSTY:
- Yavnyy: (Triggery ↔ Testy) prevraschaem priznaki v proveryaemye trebovaniya.
- Skrytyy #1: (Infoteoriya ↔ Kachestvo) otchet s faktami.
- Skrytyy #2: (Memory ↔ Uluchshenie) istoriya progonov prigodna dlya analiza.

ZEMNOY ABZATs:
Odin vyzov ekrana i detektorov na keys, taymaut. Logi - JSON v data/test/ui.

# c=a+b"""
from __future__ import annotations
from typing import Dict, Any, List
import os, json, time, http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "test", "ui")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "cases.json")
LAST = os.path.join(DIR, "last_result.json")

def _read(p: str, d: Any) -> Any:
    if not os.path.exists(p):
        with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

def _write(p: str, o: Any) -> None:
    with open(p,"w",encoding="utf-8") as f: json.dump(o,f,ensure_ascii=False,indent=2)

def add_case(case: Dict[str, Any]) -> Dict[str, Any]:
    data = _read(FILE, {"cases": []})
    data["cases"].append(case)
    _write(FILE, data)
    return {"ok": True, "count": len(data["cases"])}

def list_cases() -> Dict[str, Any]:
    return _read(FILE, {"cases": []})

def clear_cases() -> Dict[str, Any]:
    _write(FILE, {"cases": []})
    return {"ok": True}

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
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

def run_all() -> Dict[str, Any]:
    cases = list_cases().get("cases", [])
    results: List[Dict[str, Any]] = []
    passed = 0
    for cs in cases:
        kind = (cs.get("kind") or "").lower()
        params = cs.get("params") or {}
        timeout = int(cs.get("timeout_ms", 2000))
        t0 = time.time()
        ok = False
        while (time.time()-t0)*1000 <= max(100, timeout):
            scr = _get("/desktop/rpa/screen")
            if not scr.get("ok"):
                time.sleep(0.2); continue
            png = scr.get("png_b64","")
            if kind == "ocr_contains":
                r = _post("/desktop/rpa/ocr_contains", {"png_b64": png, "needle": params.get("text",""), "lang": params.get("lang","eng+rus")})
                ok = bool(r.get("ok") and r.get("found"))
            elif kind == "template_match":
                r = _post("/desktop/vision/template/find", {"screen_b64": png, "template_b64": params.get("template_b64",""), "threshold": float(params.get("threshold", 0.78))})
                ok = bool(r.get("ok"))
            if ok: break
            time.sleep(0.2)
        results.append({"name": cs.get("name","case"), "ok": ok, "elapsed_ms": int((time.time()-t0)*1000)})
        if ok: passed += 1
    out = {"ok": True, "total": len(cases), "passed": passed, "failed": len(cases)-passed, "results": results}
    _write(LAST, out)
    return out

def export_json() -> Dict[str, Any]:
    data = _read(LAST, {"ok": True, "total": 0, "passed": 0, "failed": 0, "results": []})
    return {"ok": True, "report": data}