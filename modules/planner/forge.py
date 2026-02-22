# -*- coding: utf-8 -*-
"""
modules/planner/forge.py — generator planov deystviy agenta (bez vypolneniya).

Naznachenie:
- Prevratit tsel (stroka) i «sensory» (okna/zhurnal) v determinirovannuyu ochered shagov.
- Shagi — chistye slovari (JSON), ispolnyaemye pozzhe runner'om (iteratsiya A4).

Skhema shaga:
  {
    "op": "hotkey|type|click_box|wait_template|sleep|save_as|open_app|ensure_focus",
    "args": {...},
    "meta": {"hint":"...", "safety":"safe|risky"}
  }

Publichnye funktsii:
- plan(goal:str, sense:dict) -> List[dict]
- merge_queue(new:List[dict]) -> int (dobavlyaet v obschuyu ochered)
- queue() -> List[dict]
- clear() -> None

MOSTY:
- Yavnyy: (Sense ↔ Plan) ispolzuem /sense dannye dlya utochneniya plana.
- Skrytyy #1: (Infoteoriya ↔ UX) tsel na estestvennom yazyke mappitsya na protokol deystviy.
- Skrytyy #2: (Kibernetika ↔ Bezopasnost) pomechaem shagi safety=... dlya posleduyuschey filtratsii.

ZEMNOY ABZATs:
Poka bez vypolneniya i bez pobochnykh effektov. Ochered — v pamyati protsessa.
Shablony namereniy — prostye evristiki i klyuchevye slova (rus/angl).

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, List
import re, time, threading
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_Q_LOCK = threading.Lock()
_QUEUE: List[Dict[str, Any]] = []

def queue() -> List[Dict[str, Any]]:
    with _Q_LOCK:
        return [dict(x) for x in _QUEUE]

def clear() -> None:
    with _Q_LOCK:
        _QUEUE.clear()

def merge_queue(new: List[Dict[str, Any]]) -> int:
    with _Q_LOCK:
        _QUEUE.extend(new or [])
        return len(_QUEUE)

# -------- intent heuristics --------
def _has(s: str, *words: str) -> bool:
    s = s.lower()
    return any(w.lower() in s for w in words)

def _goal_notepad_save(goal: str) -> List[Dict[str, Any]]:
    # Windows Notepad — WIN+R → notepad → type → CTRL+S → path → ENTER
    return [
        {"op":"hotkey","args":{"keys":"WIN+R"},"meta":{"hint":"Open Run","safety":"safe"}},
        {"op":"type","args":{"text":"notepad"},"meta":{"hint":"Type notepad","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"ENTER"},"meta":{"hint":"Launch Notepad","safety":"safe"}},
        {"op":"ensure_focus","args":{"app_like":"Notepad"},"meta":{"hint":"Focus Notepad","safety":"safe"}},
        {"op":"type","args":{"text":"Ester pokazyvaet shagi. Privet!"},"meta":{"hint":"Type sample text","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"CTRL+S"},"meta":{"hint":"Save dialog","safety":"safe"}},
        {"op":"save_as","args":{"path":"%USERPROFILE%\\Desktop\\demo_ester.txt"},"meta":{"hint":"Set path","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"ENTER"},"meta":{"hint":"Confirm save","safety":"safe"}},
    ]

def _goal_textedit_save(goal: str) -> List[Dict[str, Any]]:
    # macOS TextEdit — CMD+SPACE → TextEdit → ENTER → CMD+N → type → CMD+S → path → ENTER
    return [
        {"op":"hotkey","args":{"keys":"CMD+SPACE"},"meta":{"hint":"Spotlight","safety":"safe"}},
        {"op":"type","args":{"text":"TextEdit"},"meta":{"hint":"Type TextEdit","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"ENTER"},"meta":{"hint":"Launch","safety":"safe"}},
        {"op":"ensure_focus","args":{"app_like":"TextEdit"},"meta":{"hint":"Focus TextEdit","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"CMD+N"},"meta":{"hint":"New file","safety":"safe"}},
        {"op":"type","args":{"text":"Ester pishet v TextEdit"},"meta":{"hint":"Type sample text","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"CMD+S"},"meta":{"hint":"Save dialog","safety":"safe"}},
        {"op":"save_as","args":{"path":"~/Desktop/demo_ester.txt"},"meta":{"hint":"Set path","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"ENTER"},"meta":{"hint":"Confirm save","safety":"safe"}},
    ]

def _goal_open_browser(goal: str) -> List[Dict[str, Any]]:
    # Universalno: otkryt brauzer i nuzhnyy URL (esli nayden v goal)
    m = re.search(r"(https?://[^\s]+)", goal, flags=re.I)
    url = m.group(1) if m else "https://example.com"
    return [
        {"op":"open_app","args":{"app_like":"browser"},"meta":{"hint":"Open default browser","safety":"safe"}},
        {"op":"type","args":{"text":url},"meta":{"hint":"Type URL","safety":"safe"}},
        {"op":"hotkey","args":{"keys":"ENTER"},"meta":{"hint":"Navigate","safety":"safe"}}
    ]

def _goal_generic_search(goal: str) -> List[Dict[str, Any]]:
    # Generalizovannyy «pokaz»: otkryt poisk OS, nabrat tekst
    return [
        {"op":"hotkey","args":{"keys":"WIN+S"},"meta":{"hint":"OS search","safety":"safe"}},
        {"op":"type","args":{"text":goal},"meta":{"hint":"Type query","safety":"safe"}},
    ]

def plan(goal: str, sense: Dict[str, Any]) -> List[Dict[str, Any]]:
    g = (goal or "").strip()
    if not g:
        return []
    # OS hint (po spisku okon)
    windows = (sense.get("windows") or {}).get("windows") or []
    titles = " ".join([str(w.get("title","")) for w in windows]).lower()
    on_macos = "finder" in titles or "textedit" in titles
    on_windows = "notepad" in titles or "explorer" in titles

    chain: List[Dict[str, Any]] = []
    if _has(g, "notepad", "bloknot") or (on_windows and _has(g,"sokhranit","save","fayl")):
        chain = _goal_notepad_save(g)
    elif _has(g, "textedit") or (on_macos and _has(g,"sokhranit","save","fayl")):
        chain = _goal_textedit_save(g)
    elif _has(g, "brauzer","browser","chrome","edge","safari","firefox","url","http"):
        chain = _goal_open_browser(g)
    else:
        chain = _goal_generic_search(g)

    # Obschie uluchsheniya plana, opirayas na sense
    # 1) Esli zhurnal soderzhit nedavniy fail — stavim korotkuyu zaderzhku pered sleduyuschim deystviem
    jtail = (sense.get("journal") or {}).get("items") or []
    recent_fail = any((it.get("event","").lower() in ("template_fail","ocr_fail","safe_step_fail")) for it in jtail[-10:])
    if recent_fail:
        chain.insert(0, {"op":"sleep","args":{"ms":300},"meta":{"hint":"Stabilize after fail","safety":"safe"}})

    # 2) Esli ekran pust-zaglushka, dobavim ensure_focus posle otkrytiya
    if (sense.get("screen") or {}).get("source") == "fallback_blank":
        chain.append({"op":"ensure_focus","args":{"app_like":"active"},"meta":{"hint":"Focus active window","safety":"safe"}})

    return chain