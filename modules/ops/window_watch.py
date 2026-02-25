# -*- coding: utf-8 -*-
"""modules/ops/window_watch.py ​​- “zhivoy playbufer”: otslezhivanie aktivnogo okna i avtoprimenenie khotkeev.

Ideaya:
- Fonovyy potok (daemon=False) s periodicheskim oprosom aktivnogo okna.
- Pri smene zagolovka → vyzvat profile_mix.apply_for_title(title).

Control:
- start(interval_ms=800), stop(), status()

NOTE:
- Realizatsiya aktivnogo okna uproschennaya: na Windows cherez GetForegroundWindow + GetWindowText,
  na Linux - cherez `xdotool getactivewindow getwindowname` (nuzhen xdotool). Esli nedostupno - tikhiy no-op.

MOSTY:
- Yavnyy: (Sensor OS ↔ Motorika) refleks na pereklyuchenie vnimaniya.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) minimalnyy opros bez demonov i blokirovok.
- Skrytyy #2: (Kibernetika ↔ Volya) avtomaticheski “vstavlyaet” nuzhnye khotkei pri fokuse.

ZEMNOY ABZATs:
Obychnyy potok v protsesse web-prilozheniya, upravlyaemyy REST. Nikakikh vneshnikh servisov.

# c=a+b"""
from __future__ import annotations
import platform, threading, time, subprocess, ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any
from modules.thinking.profile_mix import apply_for_title
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_state: Dict[str, Any] = {"thr": None, "running": False, "last_title": None, "interval_ms": 800}

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

def _active_title_windows() -> Optional[str]:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return None
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value.strip() or None

def _active_title_linux() -> Optional[str]:
    try:
        out = subprocess.check_output("xdotool getactivewindow getwindowname", shell=True, text=True, stderr=subprocess.DEVNULL)
        return (out or "").strip() or None
    except Exception:
        return None

def _get_active_title() -> Optional[str]:
    if platform.system().lower().startswith("win"):
        return _active_title_windows()
    return _active_title_linux()

def _worker():
    _state["running"] = True
    while _state["running"]:
        try:
            title = _get_active_title()
            if title and title != _state.get("last_title"):
                _state["last_title"] = title
                apply_for_title(title)
                try:
                    _mirror_background_event(
                        f"[WINDOW_WATCH_TITLE] {title}",
                        "window_watch",
                        "title_change",
                    )
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(max(0.1, (_state.get("interval_ms") or 800) / 1000.0))
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
            f"[WINDOW_WATCH_START] interval_ms={_state['interval_ms']}",
            "window_watch",
            "start",
        )
    except Exception:
        pass
    return {"ok": True, "running": True, "interval_ms": _state["interval_ms"]}

def stop() -> Dict[str, Any]:
    _state["running"] = False
    try:
        _mirror_background_event(
            "[WINDOW_WATCH_STOP]",
            "window_watch",
            "stop",
        )
    except Exception:
        pass
    return {"ok": True, "running": False}

def status() -> Dict[str, Any]:
    return {"ok": True, "running": bool(_state.get("running")), "interval_ms": int(_state.get("interval_ms") or 800), "last_title": _state.get("last_title")}