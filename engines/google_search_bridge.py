# -*- coding: utf-8 -*-
"""engines/google_search_bridge.py

Most dlya kontroliruemogo dostupa Ester k web-poisku cherez Google Custom Search.

Zadacha etoy versii (December 2025):
- Temporarily ubrat vse "myagkie" filtry dlya samoy Ester;
- Ostavit odin yavnyy "rubilnik" cherez ENV (ESTER_NET_HARD_KILL), esli nuzhno polnostyu
  vyklyuchit setevoy search;
- Save kontrakt funktsii search(...) i format answer.

Mosty:
- Yavnyy: volya/avtonomiya ↔ HTTP Google CSE.
- Skrytyy #1: rezultaty mogut skladyvatsya v pamyat na drugikh sloyakh.
- Skrytyy #2: flag ESTER_NET_HARD_KILL daet cheloveku edinstvennyy "zhestkiy stop".

Zemnoy abzats:
Inzhenerno eto kak otdelnyy avtomat v schitke, kotoryy vsegda vklyuchen,
esli tolko ty sam ne polozhil ryadom krasnyy rubilnik "KILL". Provodka
(net_bridge/web_search) ostaetsya prezhney, my prosto ubrali lishnie
promezhutochnye predokhraniteli.

# c = a + b"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:  # pragma: but the carpet can be replaced in tests
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

TIMEOUT_S = float(os.getenv("ESTER_NET_TIMEOUT_SEC", "10"))


def _mode() -> str:
    """We leave the A/B flag for compatibility, but in this version it is
    does not restrict access to the network. Used as a mark only
    in the answer."""
    return (os.getenv("ESTER_NET_SEARCH_AB") or "B").strip().upper() or "B"


def _hard_kill_enabled() -> bool:
    v = (os.getenv("ESTER_NET_HARD_KILL") or "").strip()
    return v in ("1", "true", "True", "YES", "yes")


def _get_creds() -> Optional[Dict[str, str]]:
    key = (os.getenv("GOOGLE_API_KEY") or "").strip()
    cx = (os.getenv("GOOGLE_CX") or "").strip()
    if not key or not cx:
        return None
    return {"key": key, "cx": cx}


def is_ready() -> bool:
    """A quick check to see if the bridge can work at all (without taking into account politics)."""
    return requests is not None and _get_creds() is not None and not _hard_kill_enabled()


def _decide_allow(source: str, autonomy: Dict[str, Any]) -> bool:
    """VREMENNAYa politika dopuska v set.

    Seychas logika predelno prostaya:
    - esli vklyuchen ESTER_NET_HARD_KILL -> vsegda False;
    - inache True dlya lyubogo source ("operator", "ester", i t.d.).

    Kogda budem delat "krasivuyu politiku", syuda vernetsya razbor autonomy
    i profiley will."""
    if _hard_kill_enabled():
        return False
    return True


def _run_google_cse(query: str, max_items: int) -> Dict[str, Any]:
    """
    Nizkourovnevyy vyzov Google Custom Search.
    """
    if requests is None:
        return {"ok": False, "error": "requests_not_available", "items": []}

    creds = _get_creds()
    if not creds:
        return {"ok": False, "error": "google_creds_missing", "items": []}

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": creds["key"],
        "cx": creds["cx"],
        "q": query,
        "num": max_items,
    }

    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT_S)
    except Exception as e:  # pragma: no cover - setevye sboi ne determinirovany
        logger.warning("google_search_bridge: request_failed: %r", e)
        return {"ok": False, "error": f"request_failed:{e!r}", "items": []}

    if resp.status_code == 400:
        return {"ok": False, "error": "400_bad_request_google", "items": []}

    try:
        resp.raise_for_status()
    except Exception as e:
        logger.warning("google_search_bridge: bad_status(%s): %r", resp.status_code, e)
        return {"ok": False, "error": f"bad_status:{resp.status_code}", "items": []}

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("google_search_bridge: json_error: %r", e)
        return {"ok": False, "error": "json_error", "items": []}

    raw_items: List[Dict[str, Any]] = list(data.get("items") or [])[:max_items]
    items: List[Dict[str, Any]] = []
    for it in raw_items:
        items.append(
            {
                "title": (it.get("title") or "").strip(),
                "link": (it.get("link") or "").strip(),
                "snippet": (it.get("snippet") or "").strip(),
            }
        )

    return {"ok": bool(items), "error": None if items else "no_results", "items": items}


def search(query: str, limit: int, source: str, autonomy: Dict[str, Any]) -> Dict[str, Any]:
    """Vypolnit kontroliruemyy poisk.

    Kontrakt otveta sokhranyaem sovmestimym:

    {
      "ok": bool,
      "reason": str, # esli ok == False
      "mode": "A"|"B"|...,
      "source": "...",
      "query": "...",
      "items": [
        {"title": "...", "link": "...", "snippet": "..."},
        ...
      ]
    }"""
    mode = _mode()
    src = (source or "operator").strip().lower() or "operator"
    q = (query or "").strip()

    if not q:
        return {
            "ok": False,
            "reason": "empty_query",
            "mode": mode,
            "source": src,
            "query": q,
            "items": [],
        }

    # Admission policy (temporarily maximum permissive).
    if not _decide_allow(src, autonomy or {}):
        return {
            "ok": False,
            "reason": "not_allowed_by_policy",
            "mode": mode,
            "source": src,
            "query": q,
            "items": [],
        }

    core_res = _run_google_cse(q, max_items=max(limit or 1, 1))

    if not core_res.get("ok"):
        return {
            "ok": False,
            "reason": core_res.get("error") or "search_failed",
            "mode": mode,
            "source": src,
            "query": q,
            "items": [],
        }

    return {
        "ok": True,
        "reason": "",
        "mode": mode,
        "source": src,
        "query": q,
        "items": core_res.get("items") or [],
    }


if __name__ == "__main__":  # small manual test
    # Earth test: launched from the console, without Flask.
    demo_autonomy: Dict[str, Any] = {"scope": {"network": True}}
    out = search("RTX 5090 novosti 2025", limit=3, source="ester", autonomy=demo_autonomy)
    from pprint import pprint

    pprint(out)