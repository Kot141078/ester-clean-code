# -*- coding: utf-8 -*-
"""
modules/vision/triggers.py — triggery ekrana (OCR/shablon → deystvie).

Tipy triggerov:
- ocr_contains: {"text":"...", "lang":"eng+rus"}
- template_match: {"template_b64":"...", "threshold":0.78}

Deystviya:
- workflow: {"name":"wf_name"}
- macro: {"name":"type_text", "args":{"text":"..."}}
- mix_apply: {"title":"..."}             # primenit miks/profil dlya okna po zagolovku (profile_mix.apply_for_title)
- hotkey: {"seq":"CTRL+S"}

Khranilische: data/vision/triggers.json
Opros: fon. potok s periodom N ms, beret /desktop/rpa/screen i /desktop/metrics (esli est), uchityvaet content_pauser.

MOSTY:
- Yavnyy: (Zrenie ↔ Deystvie) uvidel → sdelal.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) yavnye detektory (OCR/shablon) i determinirovannyy tsikl.
- Skrytyy #2: (Kibernetika ↔ Kontrol) «pauza po kontentu» kak tormoz po srede.

ZEMNOY ABZATs:
Nikakikh demonov. Obychnyy Thread s REST-knopkoy start/stop. Vse fayly — lokalnye JSON.

# c=a+b
"""
from __future__ import annotations
import os, json, threading, time
from typing import Dict, Any, List, Optional

import http.client
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR = os.path.join(ROOT, "data", "vision")
FILE = os.path.join(DIR, "triggers.json")

_state: Dict[str, Any] = {"running": False, "thr": None, "interval_ms": 800, "last_fire": None}

def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": time.time()}
        try:
            from modules.memory import store  # type: ignore
            memory_add("dialog", text, meta=meta)
        except Exception:
            pass
        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if False:
                pass
        except Exception:
            pass
    except Exception:
        pass

def _ensure():
    os.makedirs(DIR, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"triggers": []}, f, ensure_ascii=False, indent=2)

def _load() -> Dict[str, Any]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(obj: Dict[str, Any]) -> None:
    _ensure()
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def list_triggers() -> List[Dict[str, Any]]:
    return (_load()).get("triggers", [])

def add_trigger(spec: Dict[str, Any]) -> Dict[str, Any]:
    obj = _load()
    arr = obj.get("triggers", [])
    arr.append(spec)
    obj["triggers"] = arr
    _save(obj)
    return {"ok": True, "count": len(arr)}

def clear_triggers() -> Dict[str, Any]:
    _save({"triggers": []})
    return {"ok": True}

# --- helpers: HTTP ---
def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=8.0)
    conn.request("GET", path)
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try:
        return json.loads(t)
    except Exception:
        return {"ok": False, "raw": t}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=12.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try:
        return json.loads(t)
    except Exception:
        return {"ok": False, "raw": t}

def _content_allowed() -> bool:
    st = _get("/guard/status")
    if not st.get("ok"):  # net guarda — propuskaem
        return True
    return bool(st.get("allowed", True))

# --- detection actions ---
def _fire_action(act: Dict[str, Any]) -> Dict[str, Any]:
    t = (act.get("type") or "").lower()
    if t == "workflow":
        return _post("/rpa/workflows/run", {"name": act.get("name","")})
    if t == "macro":
        # unifitsirovannaya ruchka makrosov — cherez workflows (edinichnyy shag)
        name = act.get("name","")
        args = act.get("args",{})
        spec = {"name": f"tmp_{name}", "steps":[{"macro": name, "args": args}]}
        try:
            # odnorazovyy zapusk cherez spets-ruchku
            return _post("/rpa/workflows/run_inline", spec)
        except Exception:
            # esli net run_inline — sozdadim i vypolnim vremennyy workflow
            _post("/rpa/workflows/save", spec)  # sovmestimo s suschestvuyuschim API (esli est)
            return _post("/rpa/workflows/run", {"name": spec["name"]})
    if t == "mix_apply":
        title = act.get("title","")
        return _post("/profiles/mix/apply", {"title": title})
    if t == "hotkey":
        return _post("/desktop/window/hotkey", {"seq": act.get("seq","")})
    return {"ok": False, "error": "unknown_action"}

# --- detectors (OCR/Template) cherez uzhe suschestvuyuschie ruchki ---
def _match_ocr(png_b64: str, text: str, lang: str) -> bool:
    # ispolzuem uzhe suschestvuyuschiy /desktop/rpa/ocr_contains
    res = _post("/desktop/rpa/ocr_contains", {"png_b64": png_b64, "needle": text, "lang": lang or "eng+rus"})
    return bool(res.get("ok") and res.get("found"))

def _match_tmpl(png_b64: str, tb64: str, thr: float) -> bool:
    res = _post("/desktop/vision/template/find", {"screen_b64": png_b64, "template_b64": tb64, "threshold": float(thr or 0.78)})
    return bool(res.get("ok"))

def _worker():
    _state["running"] = True
    while _state["running"]:
        try:
            if not _content_allowed():
                time.sleep((_state.get("interval_ms") or 800)/1000.0)
                continue
            scr = _get("/desktop/rpa/screen")
            if not scr.get("ok"):
                time.sleep((_state.get("interval_ms") or 800)/1000.0)
                continue
            png = scr.get("png_b64","")
            for trig in list_triggers():
                kind = (trig.get("kind") or "").lower()
                cond = trig.get("cond") or {}
                act = trig.get("action") or {}
                hit = False
                if kind == "ocr_contains":
                    hit = _match_ocr(png, cond.get("text",""), cond.get("lang","eng+rus"))
                elif kind == "template_match":
                    hit = _match_tmpl(png, cond.get("template_b64",""), float(cond.get("threshold") or 0.78))
                if hit:
                    _state["last_fire"] = {"ts": int(time.time()), "trig": trig}
                    _post("/attention/journal/append", {"event":"trigger_fire","detail": trig})
                    _fire_action(act)
                    try:
                        _mirror_background_event(
                            f"[VISION_TRIGGER_FIRE] kind={kind}",
                            "vision_triggers",
                            "fire",
                        )
                    except Exception:
                        pass
                    # anti-drebezg: nebolshaya pauza
                    time.sleep(0.4)
                    break
        except Exception:
            try:
                _mirror_background_event(
                    "[VISION_TRIGGER_ERROR]",
                    "vision_triggers",
                    "error",
                )
            except Exception:
                pass
            pass
        time.sleep((_state.get("interval_ms") or 800)/1000.0)
    _state["thr"] = None

def start(interval_ms: int = 800) -> Dict[str, Any]:
    if _state.get("running"):
        _state["interval_ms"] = int(interval_ms)
        return {"ok": True, "running": True, "interval_ms": _state["interval_ms"]}
    _state["interval_ms"] = int(interval_ms)
    thr = threading.Thread(target=_worker, daemon=True)
    _state["thr"] = thr; _state["running"] = True
    thr.start()
    try:
        _mirror_background_event(
            f"[VISION_TRIGGER_START] interval_ms={_state['interval_ms']}",
            "vision_triggers",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "running": True, "interval_ms": _state["interval_ms"]}

def stop() -> Dict[str, Any]:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[VISION_TRIGGER_STOP]",
            "vision_triggers",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "running": False}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "interval_ms": int(_state.get("interval_ms") or 800), "last_fire": _state.get("last_fire")}