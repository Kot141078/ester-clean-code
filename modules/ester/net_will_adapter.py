# -*- coding: utf-8 -*-
# Modul svyazki voli Ester, setevogo mosta i pamyati.
#
# Naznachenie:
# - Dat volevomu planirovschiku ponyatnyy interfeys:
#   * kogda mozhno ispolzovat vneshniy poisk,
#   * kakim endpointom,
#   * kak fiksirovat eto v pamyati kak osoznannoe deystvie.
# - Ne vmeshivatsya v kaskad myshleniya i yadro pamyati: tolko nadstroyka.
#
# Mosty:
# - Yavnyy: will_plan_ext ↔ net/search.
# - Skrytyy #1: net_will_adapter ↔ /ester/autonomy/map.
# - Skrytyy #2: net_will_adapter ↔ memory.events_unified_adapter.
#
# Zemnoy abzats:
# Kak blok v PLK nad liniey: on ne perepaivaet silovuyu chast,
# a tolko reshaet, kogda i chto vklyuchit, i zapisyvaet "vklyuchal po prichine".

from __future__ import annotations

import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from engines import google_search_bridge  # type: ignore
except Exception:  # pragma: no cover
    google_search_bridge = None  # type: ignore

# memory events (optsionalno)
_events_mod = None
try:  # pragma: no cover - myagkaya integratsiya
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
    """
    Rasshiryaet plan voli setevymi zadachami.
    Ne menyaet suschestvuyuschie polya, tolko dobavlyaet novye tasks[*].
    """
    plan = dict(base_plan or {})
    tasks: List[Dict[str, Any]] = list(plan.get("tasks") or [])

    if google_search_bridge is None or not google_search_bridge.is_ready():
        plan["tasks"] = tasks
        return plan

    mode = (os.getenv("ESTER_NET_SEARCH_AB") or "A").strip().upper() or "A"
    allow_ester = (os.getenv("ESTER_NET_SEARCH_ALLOW_ESTER") or "0").strip() in ("1", "true", "True")
    scope = (autonomy.get("scope") or {}) if isinstance(autonomy, dict) else {}
    net_ok = bool(scope.get("network", False))

    # 1) Zadacha dlya operatora — ruchnoy bezopasnyy vyzov mosta.
    tasks.append(
        {
            "id": "net_search_operator_manual",
            "kind": "network",
            "title": "Ruchnoy veb-poisk cherez most",
            "reason": "Operator mozhet zaprosit vneshniy poisk cherez /ester/net/search.",
            "safe_auto": False,
            "needs_consent": False,
            "area": "network",
            "payload": {
                "endpoint": "/ester/net/search",
                "source": "operator",
            },
        }
    )

    # 2) Zadacha dlya samoy Ester — ispolzovat poisk kak chast myshleniya.
    if mode == "B" and allow_ester and net_ok:
        tasks.append(
            {
                "id": "net_search_ester_contextual",
                "kind": "network",
                "title": "Kontekstnyy veb-poisk po vole Ester",
                "reason": "Ester mozhet zaprashivat vneshniy poisk dlya utochneniya faktov.",
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
    """
    Zafiksirovat setevoy poisk kak osoznannoe deystvie.
    Politika:
    - Esli net adaptera sobytiy — tikho vykhodim.
    - A-rezhim: logiruem tolko metadannye.
    - B-rezhim: mozhno dobavit verkhniy rezultat.
    """
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
    """
    Vypolnit poisk cherez google_search_bridge i, pri uspekhe, zapisat sobytie.
    Ispolzuetsya marshrutom /ester/net/search_logged i mozhet vyzyvatsya ee kaskadom.
    """
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