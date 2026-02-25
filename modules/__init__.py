
# -*- coding: utf-8 -*-
from __future__ import annotations
import importlib
import logging
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

"""modules/__init__.py - shlyuz Ester s aliasami i optsionalnymi patchami.
Additional information:
- Aliasy: listeners/listners, messaging, quality, memory (kak ranshe).
- Optionalnyy RouteGuard (FastAPI/Flask) pri `ESTER_ROUTE_GUARD=1`.

Zemnoy abzats:
Inogda nuzhno “podklyuchit remen bezopasnosti” dlya routov - bez pravok chuzhogo koda.
ENV‑flag vklyuchaet berezhnyy patching v rantayme.
# c=a+b"""

# --- Optional guarded routes ---
log = logging.getLogger(__name__)
__INIT_WARNINGS__: list[str] = []


def _debug_imports_enabled() -> bool:
    return (os.getenv("ESTER_DEBUG_IMPORTS", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}


def _record_init_warning(step: str, exc: BaseException) -> None:
    msg = f"{step}: {exc.__class__.__name__}: {exc}"
    __INIT_WARNINGS__.append(msg)
    if _debug_imports_enabled():
        print(f"[modules.__init__] {msg}")
    log.debug("modules init warning: %s", msg)


def _truthy(raw: str, default: bool = False) -> bool:
    s = str(raw if raw is not None else ("1" if default else "0")).strip().lower()
    return s in {"1", "true", "yes", "on", "y"}


def _install_offline_network_deny() -> None:
    # Early in-process hard gate for closed_box/offline runtime.
    if not _truthy(os.getenv("ESTER_OFFLINE", "1"), default=True):
        return
    try:
        mod = importlib.import_module("modules.runtime.network_deny")
        mode_raw = str(os.getenv("ESTER_NET_DENY_MODE", "") or "").strip().upper()
        if mode_raw not in {"A", "B"}:
            mode_raw = str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper()
            mode_raw = "B" if mode_raw == "B" else "A"
        rep = mod.install_network_deny(  # type: ignore[attr-defined]
            {
                "mode": mode_raw,
                "allow_cidrs": os.getenv("ESTER_NET_ALLOW_CIDRS", ""),
                "allow_hosts": os.getenv("ESTER_NET_ALLOW_HOSTS", ""),
            }
        )
        if (not bool(rep.get("installed"))) and mode_raw == "B":
            os.environ["ESTER_VOLITION_SLOT"] = "A"
            __INIT_WARNINGS__.append("network_deny_install_failed:slot_b_forced_to_a")
    except Exception as e:
        _record_init_warning("network_deny", e)
        if str(os.getenv("ESTER_VOLITION_SLOT", "A") or "A").strip().upper() == "B":
            os.environ["ESTER_VOLITION_SLOT"] = "A"
            __INIT_WARNINGS__.append("network_deny_exception:slot_b_forced_to_a")


_install_offline_network_deny()


if os.getenv("ESTER_ROUTE_GUARD","0") not in {"0","","false","False"}:
    try:
        importlib.import_module("modules.compat.route_guard")
    except Exception as e:
        _record_init_warning("route_guard", e)

# 1) Populyarnye simvoly iz modules.init
events_bus = None
telegram_feed_store = None
try:
    mod_init = importlib.import_module("modules.init")
    events_bus = getattr(mod_init, "events_bus", None)
    telegram_feed_store = getattr(mod_init, "telegram_feed_store", None)
except Exception as e:
    _record_init_warning("modules.init", e)

# 2) Re-export of popular agents (if any)
task_tutor = None
desktop_agent = None
try:
    from .agents import task_tutor, desktop_agent  # type: ignore
except Exception as e:
    _record_init_warning("modules.agents", e)

# 3) Karta aliasov
_ALIAS_PKGS = {
    "listeners": "listeners",
    "listners": "listeners",
    "messaging": "messaging",
    "quality": "quality",
    "memory": "memory",
    "selfcheck": "modules.self.selfcheck",
    "selfmanage": "modules.self",
}

def __getattr__(name: str):
    # unittest discovery checks package.load_tests; keep it absent unless callable is declared explicitly.
    if name == "load_tests":
        raise AttributeError("modules has no load_tests hook")
    target = _ALIAS_PKGS.get(name)
    if target:
        try:
            return importlib.import_module(target)
        except Exception as e:
            raise AttributeError(f"modules: cannot alias '{name}' -> '{target}': {e}")
    try:
        return importlib.import_module(f"modules.{name}")
    except Exception as e:
        try:
            return importlib.import_module(name)
        except Exception:
            raise AttributeError(f"modules: no attribute '{name}': {e}")

__all__ = ["events_bus", "telegram_feed_store", "task_tutor", "desktop_agent", "__INIT_WARNINGS__"]
