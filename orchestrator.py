# -*- coding: utf-8 -*-
"""
orchestrator.py — dispetcher fonovykh moduley Ester.

Ideya:
- Ne padat, esli moduley net ili oni passivnye.
- Maksimalno myagko podtsepit modules.thinking / selfevo / ingest / p2p / cron.
- Perezapuskat modul TOLKO pri padenii (isklyuchenii), a ne pri normalnom zavershenii.

Kontrakt:
- Esli modul soderzhit odnu iz funktsiy:
    start_background / run_background / run_scheduler /
    start_loop / start / run_forever / serve /
    worker / loop / run / main / bootstrap / entry
  — ona vyzyvaetsya v otdelnom daemon-potoke.
- Esli podkhodyaschey tochki vkhoda net — modul pomechaetsya kak passive.
"""

from __future__ import annotations

import os
import threading
import time
import traceback
import importlib
import inspect
from typing import Iterable, Callable, Optional, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = str(v).strip().lower()
    return v not in ("0", "false", "no", "")


def _log(msg: str) -> None:
    print(f"[orchestrator] {msg}", flush=True)


_BASE_CANDIDATES = (
    "start_background",
    "run_background",
    "run_scheduler",
    "start_loop",
    "start",
    "run_forever",
    "serve",
    "worker",
    "loop",
    "run",
    "main",
    "bootstrap",
    "entry",
)


def _pick_entry(mod, candidates: Iterable[str]) -> Optional[Callable[..., Any]]:
    # 1) Yavnye imena
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    # 2) Khevristika: lyubaya funktsiya s run/loop/worker/scheduler v imeni
    for name, fn in vars(mod).items():
        if not callable(fn):
            continue
        lname = name.lower()
        if any(x in lname for x in ("run", "loop", "worker", "scheduler", "daemon")):
            return fn

    return None


def _call_entry(fn: Callable[..., Any], app=None) -> None:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        # slozhnaya signatura — probuem dva varianta
        try:
            fn()
        except TypeError:
            fn(app)
        return

    try:
        kwargs = {}
        if app is not None:
            for name, p in sig.parameters.items():
                if name == "app":
                    kwargs[name] = app
        fn(**kwargs)
    except TypeError:
        # esli promakhnulis s kwargs — zapuskaem bez argumentov
        fn()


def _spawn(name: str, target, app=None, retry_on_error: bool = True) -> None:
    """
    Zapustit target v otdelnom potoke.
    - Pri normalnom zavershenii — vykhodim.
    - Pri isklyuchenii — log i (opts.) povtor cherez 5 sek.
    """
    def runner():
        while True:
            try:
                _log(f"starting {name}")
                _call_entry(target, app=app)
                _log(f"{name} finished (normal)")
                return  # NORMALNYY VYKhOD — BEZ PEREZAPUSKA
            except KeyboardInterrupt:
                _log(f"{name} interrupted")
                return
            except Exception:
                _log(f"{name} crashed:\n{traceback.format_exc()}")
                if not retry_on_error:
                    return
                time.sleep(5.0)

    t = threading.Thread(target=runner, name=f"ester-{name}", daemon=True)
    t.start()


def _try_module(mod_name: str, app=None, retry_on_error: bool = True) -> bool:
    try:
        mod = importlib.import_module(mod_name)
    except ImportError:
        _log(f"{mod_name}: not found")
        return False

    fn = _pick_entry(mod, _BASE_CANDIDATES)
    if not fn:
        _log(f"{mod_name}: passive (no suitable entry)")
        return False

    _spawn(mod_name, fn, app=app, retry_on_error=retry_on_error)
    return True


def start_background(app=None) -> None:
    """
    Podnyat vse, chto vklyucheno flazhkami v .env i realno suschestvuet.
    Vyzyvaetsya iz app.py odin raz (bez dubley pri debug-reloader).
    """
    # Thinking
    if _flag("THINKING_ENABLE", False):
        _try_module("modules.thinking", app=app)

    # SelfEvo
    if _flag("SELFEVO_ENABLE", False):
        _try_module("modules.selfevo", app=app)

    # CRON
    if _flag("CRON_AUTORUN", False) or _flag("CRON_ENABLE", False):
        _try_module("modules.cron", app=app)

    # P2P / LAN
    if _flag("P2P_ENABLE", False) or _flag("LAN_DISCOVERY_ENABLE", False):
        _try_module("modules.p2p", app=app)

    # Inzhest / avtodok-indeks
    if _flag("INGEST_ENABLE", False) or _flag("DOCS_AUTOINDEX_ON_START", False):
        _try_module("modules.ingest", app=app)

    # Dop. moduli iz ESTER_EXTRA_MODULES
    extra = os.getenv("ESTER_EXTRA_MODULES", "")
    for name in [x.strip() for x in extra.split(",") if x.strip()]:
        _try_module(name, app=app)

    _log("background modules scheduled")