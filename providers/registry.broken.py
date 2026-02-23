# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Drop-in refaktor vmesto bitogo providers/registry.py.
Sovmestimost:
- from providers.registry import ProviderRegistry      (OK)
- ProviderRegistry().select(name) -> dict              (OK)
- ProviderRegistry().status() -> dict                  (OK)
- ProviderRegistry.get_active() -> str                 (OK)

Povedenie: khranit aktivnogo provaydera v fayle data/app/providers/active.json,
avtomaticheski sozdaet katalogi, vedet rezervnuyu kopiyu active.prev.json.
Nikakikh vneshnikh zavisimostey.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _data_root() -> str:
    # Podderzhivaem oba varianta, kak v proekte
    return os.environ.get("ESTER_DATA_DIR") or os.environ.get("ESTER_DATA_ROOT") or os.path.abspath("data")


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
        p = _state_path()
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            ap = str(obj.get("active_provider") or "lmstudio")
            return cls(active_provider=ap)
        except FileNotFoundError:
            return cls()
        except Exception:
            # Korruptsiya fayla — otkat k prev, esli est
            try:
                with open(_state_prev_path(), "r", encoding="utf-8") as f:
                    obj = json.load(f)
                ap = str(obj.get("active_provider") or "lmstudio")
                return cls(active_provider=ap)
            except Exception:
                return cls()

    def save(self) -> None:
        _ensure_dirs()
        # rezervnaya kopiya predyduschego sostoyaniya
        try:
            if os.path.exists(_state_path()):
                with open(_state_path(), "r", encoding="utf-8") as f:
                    prev = f.read()
                with open(_state_prev_path(), "w", encoding="utf-8") as f:
                    f.write(prev)
        except Exception:
            # Rezervnaya kopiya ne kritichna
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

    # Kesh na protsess (bez obyazatelstva kross-protsessnoy sinkhronizatsii)
    _active_cache: Optional[str] = None

    def __init__(self, *_: Any, **__: Any) -> None:
        # Initsializatsiya lenivo chitaet sostoyanie
        if ProviderRegistry._active_cache is None:
            st = _State.load()
            ProviderRegistry._active_cache = st.active_provider

    # --- API ---

    @classmethod
    def get_active(cls) -> str:
        # Esli kesh pust — perechitaem s diska
        if cls._active_cache is None:
            cls._active_cache = _State.load().active_provider
        return cls._active_cache or "lmstudio"

    def select(self, name: str) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            return {"ok": False, "error": "provider name is empty"}

        # Myagkaya validatsiya izvestnykh imen, no ne zapreschaem kastomnye
        known = {"lmstudio", "openai", "anthropic", "azure", "vertexai", "ollama"}
        if name not in known:
            # prosto preduprezhdenie, kontrakt ne lomaem
            warn = f"unknown provider '{name}'"

        # Sokhranyaem novoe sostoyanie
        st = _State(active_provider=name)
        st.save()
        ProviderRegistry._active_cache = name

        resp: Dict[str, Any] = {"ok": True, "active_provider": name}
        if name not in known:
            resp["warning"] = warn  # type: ignore[name-defined]
        return resp

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "active_provider": ProviderRegistry.get_active(),
            # Ostalnoe obychno dobavlyaet sam rout (probe i t.p.),
            # no zdes ostavim polya, kotorye uzhe videlis v otvetakh:
            "authoring_backend": "local",
        }