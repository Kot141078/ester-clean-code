# -*- coding: utf-8 -*-
"""
modules/thinking/rpa_macros.py — «mysli → deystviya»: reestr RPA-makrosov dlya Ester.

Ideya: vysokourovnevye stsenarii (plany) prevraschayutsya v nizkourovnevye shagi /desktop/rpa/*.
Realizatsiya oflayn, lokalnyy HTTP k agentu 127.0.0.1:8732 cherez servernyy proksi /desktop/rpa/*.

MOSTY:
- Yavnyy: (Planirovanie ↔ Ispolnenie) makrosy svyazyvayut mysl i RPA-deystviya.
- Skrytyy #1: (Bayes ↔ Infoteoriya) shagi makrosa — ogranichennyy alfavit deystviy → nizhe entropiya oshibok.
- Skrytyy #2: (Kibernetika ↔ Arkhitektura) petlya «zamysel→akt→audit»: log makrosov popadaet v obschiy rpa.jsonl cherez agent.

ZEMNOY ABZATs:
Daet praktichnye knopki/endpointy: otkryt prilozhenie, napechatat stroku, sdelat klik. 
Podderzhivaet A/B sloty agenta avtomaticheski — bez izmeneniya kontraktov.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List, Callable
import http.client
import json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class MacroError(RuntimeError):
    """Raised when macro execution via local /desktop/rpa endpoints fails."""

def _post(path: str, payload: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=timeout)  # idem cherez servernye marshruty
    body = json.dumps(payload or {})
    headers = {"Content-Type": "application/json"}
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        obj = json.loads(data)
    except Exception as e:
        raise MacroError(f"Bad server reply: {e}: {data}")
    if not obj or not obj.get("ok"):
        raise MacroError(f"Server returned error for {path}: {obj}")
    return obj

def _get(path: str, timeout: float = 3.0) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=timeout)
    conn.request("GET", path)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        obj = json.loads(data)
    except Exception as e:
        raise MacroError(f"Bad server reply: {e}: {data}")
    if not obj or not obj.get("ok"):
        raise MacroError(f"Server returned error for {path}: {obj}")
    return obj

def step_open(app: str) -> None:
    _post("/desktop/rpa/open", {"app": app})

def step_type(text: str) -> None:
    _post("/desktop/rpa/type", {"text": text})

def step_click(x: int, y: int) -> None:
    _post("/desktop/rpa/click", {"x": int(x), "y": int(y)})

def step_ocr_click(needle: str, lang: str = "eng+rus") -> None:
    _post("/desktop/rpa/ocr_click", {"needle": needle, "lang": lang})

def step_screen() -> Dict[str, Any]:
    return _get("/desktop/rpa/screen")

# ----- Reestr makrosov -----

def macro_open_portal_and_type(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Otkryt dostupnyy brauzer i vvesti stroku (kak «puls» svyazki mysl→deystvie).
    args:
      text: chto pechatat
      app:  'chrome'|'notepad'|'xterm' (optsionalno, po umolchaniyu 'notepad' na Win, 'xterm' na Linux)
    """
    text = str(args.get("text") or "Hello from Ester")
    app = str(args.get("app") or "").strip().lower()
    if not app:
        # minimalnaya evristika: esli est Windows Chrome — ispolzuem; inache xterm
        try:
            step_open("chrome")
            app = "chrome"
        except Exception:
            try:
                step_open("notepad")
                app = "notepad"
            except Exception:
                step_open("xterm")
                app = "xterm"
    else:
        step_open(app)
    # dadim oknu vsplyt
    # (agent rabotaet bez taymingov OS; nebolshaya pauza so storony klienta ne trebuetsya, polagaemsya na OS)
    step_type(text)
    return {"ok": True, "macro": "open_portal_and_type", "app": app, "typed": len(text)}

def macro_click_text(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nayti tekst na ekrane i kliknut po nemu (tesseract TSV).
    args:
      needle: iskomaya podstroka (obyazatelno)
      lang:   'eng+rus' i t.p. (optsionalno)
    """
    needle = (args.get("needle") or "").strip()
    if not needle:
        raise MacroError("needle_required")
    lang = (args.get("lang") or "eng+rus").strip()
    step_ocr_click(needle, lang)
    return {"ok": True, "macro": "click_text", "needle": needle}

_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "open_portal_and_type": macro_open_portal_and_type,
    "click_text": macro_click_text,
}

def list_macros() -> List[str]:
    return sorted(_REGISTRY.keys())

def run_macro(name: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
    fn = _REGISTRY.get(name)
    if not fn:
        raise MacroError("macro_not_found")
    return fn(args or {})
