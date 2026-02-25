"""Ester Net Search -> Memory Bridge

Name:
- Yavnyy most mezhdu setevym poiskom i sistemoy pamyati.
- Esli dostupen events_unified_adapter or analogichnyy layer, zapisyvaet sobytie.
- Pri oshibke tikho degradiruet, ne lomaya osnovnoy potok.

Zemnoy abzats:
Kak v normalnoy inzhenernoy sisteme logirovaniya zaprosov k oborudovaniyu:
kazhdoe obraschenie k vneshnemu kanalu fiksiruetsya v zhurnale, chtoby potom mozhno
bylo vosstanovit, kto, kogda i zachem dergal liniyu."""

from __future__ import annotations

import time
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def record_net_search_event(source: str, query: str, items: List[Dict[str, Any]]) -> bool:
    """Pytaetsya zapisat fakt setevogo poiska v pamyat Ester.

    Vozvraschaet:
        True - esli udalos zapisat cherez odin iz dostupnykh adapterov,
        False - esli nichego ne sdelali (no bez vybrosa isklyucheniy)."""
    payload = {
        "ts": time.time(),
        "kind": "net_search",
        "source": source,
        "query": query,
        "items_sample": [
            {
                "title": (i.get("title") or "")[:200],
                "link": (i.get("link") or "")[:300],
            }
            for i in (items or [])[:5]
        ],
    }

    # An explicit bridge to the unified layer, if there is one.
    try:
        from modules.memory import events_unified_adapter as eua  # type: ignore

        for attr in ("register_event", "log_event", "push_event"):
            fn = getattr(eua, attr, None)
            if callable(fn):
                fn("net_search", payload)
                return True
    except Exception:
        # Quiet failure: memory should not break the network bridge.
        pass

    # Hidden bridge: if there is a generic meta/experiential API.
    try:
        from modules.memory import experience as exp  # type: ignore

        fn = getattr(exp, "add_experience", None)
        if callable(fn):
            fn("net_search", payload)
            return True
    except Exception:
        pass

    # Another hidden bridge: through the meta, if it exists.
    try:
        from modules.memory import meta as meta_mod  # type: ignore

        fn = getattr(meta_mod, "log_system_event", None)
        if callable(fn):
            fn("net_search", payload)
            return True
    except Exception:
        pass

    return False