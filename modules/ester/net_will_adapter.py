# -*- coding: utf-8 -*-
# Module for linking Esther's will, network bridge and memory.
#
# Naznachenie:
# - Give strong-willed planners a clear interface:
#   * when you can use external search,
#   * what endpoint,
#   * how to record this in memory as a conscious action.
# - Do not interfere with the cascade of thinking and the core of memory: only a superstructure.
#
# Mosty:
# - Yavnyy: will_plan_ext ↔ net/search.
# - Skrytyy #1: net_will_adapter ↔ /ester/autonomy/map.
# - Skrytyy #2: net_will_adapter ↔ memory.events_unified_adapter.
#
# Zemnoy abzats:
# Like a block in a PLC above the line: it does not solder the power part,
# but only decides when and what to turn on, and writes down “turned on for a reason.”

from __future__ import annotations

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from engines import google_search_bridge  # type: ignore
except Exception:  # pragma: no cover
    google_search_bridge = None  # type: ignore

# memory events (optional)
_events_mod = None
try:  # pragma: but the carpet is soft integration
    from modules.memory import events_unified_adapter as _events_mod  # type: ignore
except Exception:
    _events_mod = None


def _log_mode() -> str:
    return (os.getenv("ESTER_NET_SEARCH_LOG_AB") or "A").strip().upper() or "A"


def get_autonomy(app) -> Dict[str, Any]:
    client = app.test_client()
    try:
        r = client.get("/ester/autonomy/map")
        if r.status_code == 200:
            data = r.get_json(silent=True) or {}
            if "autonomy" in data:
                return data["autonomy"]
            return data
    except Exception:
        pass
    return {"scope": {"network": False}}


def extend_plan_with_net(base_plan: Dict[str, Any], autonomy: Dict[str, Any]) -> Dict[str, Any]:
    """Expands the will plan with network tasks.
    Does not change existing fields, only adds new tasks."""
    plan = dict(base_plan or {})
    tasks: List[Dict[str, Any]] = list(plan.get("tasks") or [])

    if google_search_bridge is None or not google_search_bridge.is_ready():
        plan["tasks"] = tasks
        return plan

    mode = (os.getenv("ESTER_NET_SEARCH_AB") or "A").strip().upper() or "A"
    allow_ester = (os.getenv("ESTER_NET_SEARCH_ALLOW_ESTER") or "0").strip() in ("1", "true", "True")
    scope = (autonomy.get("scope") or {}) if isinstance(autonomy, dict) else {}
    net_ok = bool(scope.get("network", False))

    # 1) The task for the operator is to manually call the bridge safely.
    tasks.append(
        {
            "id": "net_search_operator_manual",
            "kind": "network",
            "title": "Manual web search via bridge",
            "reason": "The operator can request an external search via /ester/net/search.",
            "safe_auto": False,
            "needs_consent": False,
            "area": "network",
            "payload": {
                "endpoint": "/ester/net/search",
                "source": "operator",
            },
        }
    )

    # 2) The task for Esther herself is to use search as part of thinking.
    if mode == "B" and allow_ester and net_ok:
        tasks.append(
            {
                "id": "net_search_ester_contextual",
                "kind": "network",
                "title": "Kontekstnyy veb-poisk po vole Ester",
                "reason": "Esther can request an external search to clarify facts.",
                "safe_auto": True,
                "needs_consent": True,
                "area": "network",
                "payload": {
                    "endpoint": "/ester/net/search_logged",
                    "source": "ester",
                    "log": True,
                },
            }
        )

    plan["tasks"] = tasks
    return plan


def _try_log_event(query: str, source: str, autonomy: Dict[str, Any], result: Dict[str, Any]) -> bool:
    """Zafiksirovat setevoy poisk kak osoznannoe deystvie.
    Politika:
    - Esli net adaptera sobytiy - tikho vykhodim.
    - A-rezhim: logiruem only metadannye.
    - B-rezhim: mozhno dobavit verkhniy rezultat."""
    if _events_mod is None:
        return False

    log_mode = _log_mode()
    payload: Dict[str, Any] = {
        "kind": "net_search",
        "source": source,
        "query": query,
        "autonomy_scope": autonomy.get("scope"),
        "ok": bool(result.get("ok")),
        "engine": "google_custom_search",
    }

    if log_mode == "B" and result.get("ok"):
        items = result.get("items") or []
        if items:
            payload["top"] = items[0].get("link")

    try:
        if hasattr(_events_mod, "record_event"):
            _events_mod.record_event("net_search", payload)  # type: ignore
            return True
        if hasattr(_events_mod, "save_event"):
            _events_mod.save_event("net_search", payload)  # type: ignore
            return True
        if hasattr(_events_mod, "log_event"):
            _events_mod.log_event("net_search", payload)  # type: ignore
            return True
    except Exception:
        return False

    return False


def search_and_log(app, query: str, limit: int, source: str) -> Dict[str, Any]:
    """Vypolnit poisk cherez google_search_bridge i, pri uspekhe, zapisat sobytie.
    Ispolzuetsya route /ester/net/search_logged i mozhet vyzyvatsya ee kaskadom."""
    if google_search_bridge is None or not google_search_bridge.is_ready():
        return {
            "ok": False,
            "reason": "bridge_not_ready",
        }

    autonomy = get_autonomy(app)
    result = google_search_bridge.search(
        query=query,
        limit=limit,
        source=source,
        autonomy=autonomy,
    )

    logged = False
    if result.get("ok"):
        logged = _try_log_event(query, source, autonomy, result)

    result["logged"] = bool(logged)
    return result