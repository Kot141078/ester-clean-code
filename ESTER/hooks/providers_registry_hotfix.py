# -*- coding: utf-8 -*-
from __future__ import annotations

"""Vremennyy khotfiks: esli import providers.registry padaet SyntaxError-om,
podmenyaem modul na minimalnyy shim with nuzhnym API (select/status),
chtoby /providers/select ne valilsya 500-koy. Kontrakty ne lomaem.
Ubrat fayl after pochinki providers/registry.py."""

import sys
import types
from typing import Any, Dict
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def init_app(app: Flask) -> None:  # vyzyvaetsya rantaymom ESTER/hooks/*
    try:
        # We try regular import: if the file is valid, we do nothing further.
        import providers.registry as real  # type: ignore
        getattr(real, "__dict__", None)   # forsiruem zagruzku
        return
    except SyntaxError:
        # Gotovim shim-modul "providers.registry"
        mod = types.ModuleType("providers.registry")

        class ProviderRegistry:
            _active: str = "lmstudio"

            def __init__(self, *_: Any, **__: Any) -> None:
                pass

            @classmethod
            def get_active(cls) -> str:
                return cls._active

            def select(self, name: str) -> Dict[str, Any]:
                if name:
                    self.__class__._active = name
                return {"ok": True, "active_provider": self.__class__._active}

            def status(self) -> Dict[str, Any]:
                return {
                    "ok": True,
                    "active_provider": self.__class__._active,
                    "authoring_backend": "local",
                }

        mod.ProviderRegistry = ProviderRegistry  # type: ignore[attr-defined]
        sys.modules["providers.registry"] = mod  # podmena do refaktora
    except Exception:
        # Ignore any other import errors - does not interfere with the rest of the start
        pass