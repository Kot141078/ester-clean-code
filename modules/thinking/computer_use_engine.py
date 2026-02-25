# -*- coding: utf-8 -*-
"""modules/thinking/computer_use_engine.py - tonkiy orkestrator Computer Use (offlayn).

MOSTY:
- Yavnyy: (Mentor/Workflow ↔ RPA REST) — ispolnyaet plany shagov cherez uzhe suschestvuyuschie /desktop/rpa/*,
  ne menyaya ikh kontraktov. This obespechivaet “stseplenie” myshleniya i deystviy.  # opora: rpa_record_routes → /desktop/rpa/* 
- Skrytyy No. 1: (Infoteoriya ↔ Audit) - edinyy trace na kazhdyy shag (minimalnyy bitreyt logov; gotovnost k repleyu).
- Skrytyy No. 2: (Kibernetika Ashbi ↔ Ustoychivost) - petlya “nablyudenie→reshenie→deystvie→proverka” s ozhidaniyami,
  retrayami i lokalnym avto-otkatom slota.

ZEMNOY ABZATs:
Eto “raspredelitelnaya korobka”: zhdem vidimyy priznak na ekrane (OCR), zatem akkuratno zhmem i pechataem.
Pishem podrobnyy trace, uvazhaem dry-run (WRITE=0) i, pri oshibkakh, lokalno pereklyuchaem ostavshiesya step v dry-run
(ESTER_RPA_AUTOROLLBACK=1), ne trogaya globalnye nastroyki i ne sozdavaya pobochnykh effektov.

# c=a+b"""
from __future__ import annotations

import os
import time
import json
import base64
from typing import Any, Dict, List, Optional, Tuple
from urllib import request as _rq
from urllib.error import URLError, HTTPError
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Bazovyy URL servera (edinyy stil po proektu)
GARAGE_URL = os.getenv("GARAGE_URL", "http://127.0.0.1:8000")  # sovmestimo s dampom  # :contentReference[oaicite:5]{index=5}

# A/B-slot i politika zapisi
RPA_AB = (os.getenv("ESTER_RPA_AB") or "A").strip().upper()
RPA_WRITE_INIT = bool(int(os.getenv("ESTER_RPA_WRITE", "0")))
RPA_AUTOROLLBACK = bool(int(os.getenv("ESTER_RPA_AUTOROLLBACK", "1")))

# Temporary parameters (slot B - a little more gentle)
WAIT_INTERVAL_MS = 200 if RPA_AB == "A" else 300

def _http(method: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 12.0) -> Dict[str, Any]:
    url = f"{GARAGE_URL.rstrip('/')}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload or {}).encode("utf-8")
    req = _rq.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with _rq.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
            try:
                return json.loads(raw)
            except Exception:
                return {"ok": False, "raw": raw}
    except HTTPError as e:
        return {"ok": False, "status": e.code, "error": "http_error"}
    except URLError as e:
        return {"ok": False, "error": f"url_error:{e}"}
    except Exception as e:
        return {"ok": False, "error": f"unexpected:{e}"}

def _get(path: str, timeout: float = 12.0) -> Dict[str, Any]:
    return _http("GET", path, None, timeout)

def _post(path: str, body: Dict[str, Any], timeout: float = 12.0) -> Dict[str, Any]:
    return _http("POST", path, body, timeout)

def _screen_png_b64() -> Optional[str]:
    r = _get("/desktop/rpa/screen")  # existing handle family /desktop/rpa/* # :contentReference:6шЗФ0З
    if r.get("ok") and r.get("png_b64"):
        return str(r.get("png_b64"))
    return None

def wait_ocr(text: str, lang: str = "eng+rus", timeout_ms: int = 4000, interval_ms: int = WAIT_INTERVAL_MS) -> Dict[str, Any]:
    """We are waiting for the text to appear on the screen (OCR) without changing the OCD handle contract."""
    t0 = time.time()
    tries = 0
    while (time.time() - t0) * 1000 <= max(100, int(timeout_ms)):
        img = _screen_png_b64()
        if img:
            r = _post("/desktop/rpa/ocr_contains", {"png_b64": img, "needle": text, "lang": lang})
            tries += 1
            if r.get("ok") and r.get("found"):
                return {"ok": True, "tries": tries}
        time.sleep(max(20, int(interval_ms)) / 1000.0)
    return {"ok": False, "tries": tries, "error": "timeout"}

def do_click_xy(x: int, y: int, write: bool) -> Dict[str, Any]:
    if not write:
        return {"ok": True, "dry_run": True, "x": int(x), "y": int(y)}
    return _post("/desktop/rpa/click", {"x": int(x), "y": int(y)})

def do_type_text(text: str, write: bool) -> Dict[str, Any]:
    if not write:
        return {"ok": True, "dry_run": True, "typed": len(text)}
    return _post("/desktop/rpa/type", {"text": text})

def do_open_url(url: str, browser: str, write: bool) -> Dict[str, Any]:
    if not write:
        return {"ok": True, "dry_run": True, "url": url, "browser": browser}
    return _post("/desktop/rpa/open_url", {"url": url, "browser": browser})

def run(plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Plan - spisok shagov vida:
      {"open_url":{"url":"https://example.org","browser":"system"}}
      {"wait_ocr":{"text":"OK","lang":"eng+rus","timeout_ms":5000,"interval_ms":200}}
      {"click":{"x":123,"y":456}}
      {"type":{"text":"hello"}}
      {"sleep_ms":300}

    Kontrakty suschestvuyuschikh REST-ruchek ne menyayutsya; vse adaptery - vnutri etogo fayla."""
    trace: List[Dict[str, Any]] = []
    ok = True
    write = bool(RPA_WRITE_INIT)
    rolled_back = False

    for step in plan or []:
        if not isinstance(step, dict) or not step:
            trace.append({"step": "invalid", "res": {"ok": False, "error": "bad_step"}})
            ok = False
            break

        name = next(iter(step.keys()))
        val = step.get(name) or {}

        if name == "open_url":
            r = do_open_url(str(val.get("url","")), str(val.get("browser","system")), write)
            trace.append({"step": name, "res": r})

        elif name == "wait_ocr":
            r = wait_ocr(str(val.get("text","")),
                         str(val.get("lang","eng+rus")),
                         int(val.get("timeout_ms", 4000)),
                         int(val.get("interval_ms", WAIT_INTERVAL_MS)))
            trace.append({"step": name, "res": r})
            if not r.get("ok"):
                ok = False

        elif name == "click":
            r = do_click_xy(int(val.get("x", 0)), int(val.get("y", 0)), write)
            trace.append({"step": name, "res": r})
            if not r.get("ok"):
                ok = False

        elif name == "type":
            r = do_type_text(str(val.get("text","")), write)
            trace.append({"step": name, "res": r})
            if not r.get("ok"):
                ok = False

        elif name == "sleep_ms":
            ms = max(0, int(val or 0))
            time.sleep(ms / 1000.0)
            trace.append({"step": name, "res": {"ok": True, "slept_ms": ms}})

        else:
            trace.append({"step": name, "res": {"ok": False, "error": "unknown_step"}})
            ok = False

        # Local auto-rollback for remaining steps (without external side effects)
        if RPA_AUTOROLLBACK and not rolled_back and write and (not trace[-1]["res"].get("ok")):
            write = False
            rolled_back = True
            trace.append({"step": "auto_rollback", "res": {"ok": True, "write": write}})

        # Slot B - more conservative: short pause between steps
        if RPA_AB == "B":
            time.sleep(0.05)

        if not ok:
            break

    return {
        "ok": ok,
        "ab": RPA_AB,
        "write": bool(RPA_WRITE_INIT),
        "rolled_back": bool(rolled_back),
        "trace": trace
    }