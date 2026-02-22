# -*- coding: utf-8 -*-
"""
Legkiy logger namereniy i faktov samoizmeneniya v pamyat Ester.

Trebovaniya:
- ne lomat rabotu, esli memory-adapterov net;
- ne delat setevykh vyzovov;
- ne pisat nichego v zapreschennye zony;
- byt mostom mezhdu voley/samomodom i sloyami pamyati (events / journal).

Esli nuzhnykh funktsiy v pamyati net — molcha vykhodim.
"""

import time
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _get_events_adapter():
    """Pytaemsya nayti edinyy adapter sobytiy pamyati (best-effort)."""
    try:
        from modules.memory import events_unified_adapter as ev  # type: ignore
        return ev
    except Exception:
        return None


def _emit(adapter, event: Dict[str, Any]) -> None:
    """Otpravka sobytiya v adapter, s podderzhkoy neskolkikh signatur."""
    try:
        if hasattr(adapter, "log_event"):
            adapter.log_event(event)  # type: ignore[attr-defined]
        elif hasattr(adapter, "add_event"):
            adapter.add_event(event)  # type: ignore[attr-defined]
        elif hasattr(adapter, "store_event"):
            adapter.store_event(event)  # type: ignore[attr-defined]
    except Exception:
        # Logger ne imeet prava lomat osnovnoy potok.
        return


def log_selfmod_event(source: str, body: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Fiksiruem fakt namereniya/samoizmeneniya v pamyati (esli vozmozhno)."""
    adapter = _get_events_adapter()
    if not adapter:
        return

    try:
        changes = body.get("changes") or []
        paths: List[str] = []
        for ch in changes:
            p = ch.get("path")
            if p:
                paths.append(str(p))

        event: Dict[str, Any] = {
            "ts": time.time(),
            "channel": "selfmod",
            "kind": "selfmod_propose",
            "source": source,
            "reason": body.get("reason") or "",
            "paths": paths,
            "ok": bool(result.get("ok")),
            "mode": result.get("mode"),
            "status_code": result.get("status_code"),
            "errors": result.get("errors")
                      or (result.get("result") or {}).get("errors")
                      or [],
            "note": (result.get("result") or {}).get("note"),
        }

        _emit(adapter, event)
    except Exception:
        # Nikogda ne ronyaem osnovnoy potok iz-za loggera.
        return