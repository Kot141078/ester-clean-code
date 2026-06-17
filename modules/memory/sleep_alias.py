# -*- coding: utf-8 -*-
"""Compatibility alias for the memory sleep facade.

This module delegates to the clean-code daily-cycle compatibility layer. It
does not create runtime files, read private memory, or call external services.
"""

from __future__ import annotations

import os
from typing import Any

from . import daily_cycle

_SLOT_ENV = "ESTER_MEMORY_SLEEP_AB"


def _clean_slot(value: Any = None) -> str:
    raw = str(value if value is not None else os.getenv(_SLOT_ENV, "A") or "A").strip().upper()
    return "B" if raw == "B" else "A"


def status() -> dict[str, Any]:
    data = daily_cycle.status()
    out = dict(data) if isinstance(data, dict) else {"ok": True}
    out.setdefault("ok", True)
    out["slot"] = _clean_slot(out.get("slot"))
    out["impl"] = "modules.memory.daily_cycle"
    return out


def run_cycle(*args: Any, **kwargs: Any) -> dict[str, Any]:
    data = daily_cycle.run_cycle(*args, **kwargs)
    out = dict(data) if isinstance(data, dict) else {"ok": True}
    out.setdefault("ok", True)
    out.setdefault("slot", _clean_slot())
    out["impl"] = "modules.memory.daily_cycle"
    return out


def switch_slot(slot: str = "A") -> dict[str, Any]:
    value = _clean_slot(slot)
    os.environ[_SLOT_ENV] = value
    return {"ok": True, "slot": value, "impl": "modules.memory.daily_cycle"}


__all__ = ["run_cycle", "status", "switch_slot"]
