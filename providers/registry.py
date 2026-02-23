# -*- coding: utf-8 -*-
from __future__ import annotations

"""
providers/registry.py — minimalnyy reestr aktivnogo provaydera dlya UI/routov.

Sovmestimost:
- from providers.registry import ProviderRegistry
- ProviderRegistry().select(name) -> dict
- ProviderRegistry().status() -> dict
- ProviderRegistry.get_active() -> str

Khranit aktivnyy provayder v data/app/providers/active.json
i delaet rezervnuyu kopiyu active.prev.json.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _data_root() -> str:
    return (
        os.environ.get("ESTER_DATA_DIR")
        or os.environ.get("ESTER_DATA_ROOT")
        or os.path.abspath("data")
    )


def _providers_state_dir() -> str:
    return os.path.join(_data_root(), "app", "providers")


def _state_path() -> str:
    return os.path.join(_providers_state_dir(), "active.json")


def _state_prev_path() -> str:
    return os.path.join(_providers_state_dir(), "active.prev.json")


def _ensure_dirs() -> None:
    os.makedirs(_providers_state_dir(), exist_ok=True)


@dataclass
class _State:
    active_provider: str = "lmstudio"

    @classmethod
    def load(cls) -> "_State":
        _ensure_dirs()
        try:
            with open(_state_path(), "r", encoding="utf-8") as f:
                obj = json.load(f)
            ap = str(obj.get("active_provider") or "lmstudio")
            return cls(active_provider=ap)
        except FileNotFoundError:
            return cls()
        except Exception:
            # corruption: fallback to prev
            try:
                with open(_state_prev_path(), "r", encoding="utf-8") as f:
                    obj = json.load(f)
                ap = str(obj.get("active_provider") or "lmstudio")
                return cls(active_provider=ap)
            except Exception:
                return cls()

    def save(self) -> None:
        _ensure_dirs()
        try:
            if os.path.exists(_state_path()):
                with open(_state_path(), "r", encoding="utf-8") as f:
                    prev = f.read()
                with open(_state_prev_path(), "w", encoding="utf-8") as f:
                    f.write(prev)
        except Exception:
            pass

        tmp = _state_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"active_provider": self.active_provider}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _state_path())


class ProviderRegistry:
    """
    Minimalnyy API, ozhidaemyy routami:
      - select(name) -> {ok:bool, active_provider:str}
      - status()     -> {...}
      - get_active() -> str
    """

    _active_cache: Optional[str] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        if ProviderRegistry._active_cache is None:
            ProviderRegistry._active_cache = _State.load().active_provider

    @classmethod
    def get_active(cls) -> str:
        if cls._active_cache is None:
            cls._active_cache = _State.load().active_provider
        return cls._active_cache or "lmstudio"

    def select(self, name: str) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            return {"ok": False, "error": "provider name is empty"}

        known = {"lmstudio", "openai", "anthropic", "azure", "vertexai", "ollama"}
        warn = None if name in known else f"unknown provider '{name}'"

        st = _State(active_provider=name)
        st.save()
        ProviderRegistry._active_cache = name

        resp: Dict[str, Any] = {"ok": True, "active_provider": name}
        if warn:
            resp["warning"] = warn
        return resp

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "active_provider": ProviderRegistry.get_active(),
            "authoring_backend": "local",
        }

