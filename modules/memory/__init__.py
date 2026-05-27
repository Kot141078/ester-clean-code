# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from types import ModuleType

from .bus import MemoryBus
from .journal import record_event


def _install_events_compat() -> ModuleType:
    module_name = f"{__name__}.events"
    module = sys.modules.get(module_name)
    if module is None:
        module = ModuleType(module_name)
        sys.modules[module_name] = module
    if not callable(getattr(module, "record_event", None)):
        module.record_event = record_event  # type: ignore[attr-defined]
    return module


events = _install_events_compat()


def _install_memory_bus_compat() -> ModuleType:
    module_name = f"{__name__}.memory_bus"
    module = sys.modules.get(module_name)
    if module is None:
        module = ModuleType(module_name)
        sys.modules[module_name] = module
    if not callable(getattr(module, "MemoryBus", None)):
        module.MemoryBus = MemoryBus  # type: ignore[attr-defined]
    return module


memory_bus = _install_memory_bus_compat()

__all__ = ["events", "MemoryBus", "memory_bus"]
