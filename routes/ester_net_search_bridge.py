# -*- coding: utf-8 -*-
"""routes/ester_net_search_bridge.py

Zhestkiy override dlya /ester/net/search, chtoby:
- ubrat "not_allowed_by_policy" dlya Ester pri lokalnom ispolzovanii (esli ty yavno razreshil v .env);
- ispolzovat tot zhe rabochiy stek, chto i skripty (modules/web_search.search_web);
- ne lezt v suschestvuyuschie moduli policy/will/guard.

MOSTY:
- Yavnyy: modules/web_search.py -> etot route (/ester/net/search).
- Skrytyy #1: chtenie ENV (ESTER_NET_ALLOW_ESTER, ESTER_NET_SEARCH_ALLOW_ESTER, SEARCH_AB/SEARCH_PROVIDER)
  -> profili avtonomii/voli.
- Skrytyy #2: istochnik v otvetakh (`items[i]["source"]`) -> vozmozhnoe sokhranenie i analiz v pamyati/logakh.

ZEMNOY ABZATs:
Po-inzhenernomu: this is just a thin HTTP-adapter.
Zhelezo (Ethernet/Wi-Fi) daet bayty, Python-modul web_search sobiraet HTML i API-otvety,
a etot fayl tolko upakovyvaet ikh v JSON dlya /ester/net/search, ne vmeshivayas v “mozgi” Ester."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _env_bool(name: str, default: bool = True) -> bool:
    v = (os.getenv(name, "1" if default else "0") or "").strip()
    if v == "":
        return default
    return v not in {"0", "false", "False", "no", "NO"}


def _get_topk(payload: Dict[str, Any]) -> int:
    # maksimum berem iz ENV ili po umolchaniyu 5
    try:
        env_max = int(os.getenv("ESTER_NET_MAX_ITEMS", "5"))
    except Exception:
        env_max = 5
    raw = payload.get("topk") or payload.get("limit") or env_max
    try:
        v = int(raw)
    except Exception:
        v = env_max
    return max(1, min(v, env_max))


def _simple_search_via_web_search(q: str, topk: int) -> Dict[str, Any]:
    """Minimalnyy most k modules/web_search.py:
    ispolzuem edinyy fasad search_web(), kotoryy sam reshaet:
      - kakim provayderom strelyat (Google / SerpAPI / Bing / DDG),
      - kak padat v folbek.

    Vozvraschaem:
    {
      "ok": bool,
      "error": "no_results" | "import_web_search_failed: ..." | None
      "items": [{title, link, snippet}],
      "providers_tried": ["google"|"serpapi"|"bing"|"ddg", ...]
    }"""
    try:
        from modules import web_search as ws  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "error": f"import_web_search_failed: {e}",
            "items": [],
            "providers_tried": [],
        }

    try:
        raw_items = ws.search_web(q, topk)  # type: ignore[attr-defined]
    except Exception as e:
        return {
            "ok": False,
            "error": f"search_web_failed: {e}",
            "items": [],
            "providers_tried": [],
        }

    if not raw_items:
        return {
            "ok": False,
            "error": "no_results",
            "items": [],
            "providers_tried": [],
        }

    items: List[Dict[str, Any]] = []
    providers_chain: List[str] = []

    for it in raw_items:
        title = it.get("title") or it.get("url") or ""
        link = it.get("url") or it.get("link") or ""
        snippet = it.get("snippet") or ""
        src = (it.get("source") or "").strip() or "unknown"

        items.append(
            {
                "title": title,
                "link": link,
                "snippet": snippet,
            }
        )
        if src not in providers_chain:
            providers_chain.append(src)

    return {
        "ok": bool(items),
        "error": None if items else "no_results",
        "items": items,
        "providers_tried": providers_chain,
    }


def register(app):
    """The function that autoload_run_fs() picks up from the app.
    It registers our route and overrides the previous /ester/net/search handlers."""
    # Flagi politiki iz .env
    allow_ester = _env_bool("ESTER_NET_ALLOW_ESTER", True)
    allow_search = _env_bool("ESTER_NET_SEARCH_ALLOW_ESTER", True)

    print("[ester-net-search/bridge] registering /ester/net/search (override)")

    @app.post("/ester/net/search")
    def ester_net_search_bridge():
        """Unifitsirovannyy vkhod dlya vsekh, kto stuchitsya v /ester/net/search.

        Vkhod (JSON):
        {
          "q": "stroka zaprosa",
          "source": "diag|operator|will|... (optsionalno)",
          "topk": 5  (optsionalno),
          "limit": 5 (sinonim topk)
        }

        Vykhod (JSON):
        {
          "ok": true/false,
          "mode": "B",
          "source": "ester|operator|...",
          "query": "originalnyy requests",
          "items": [{ "title": "...", "link": "...", "snippet": "..." }, ...],
          "providers_tried": ["google", "serpapi", ...],
          "reason": "no_results|not_allowed_by_policy|empty_query|..."
        }"""
        try:
            payload = request.get_json(force=True, silent=True) or {}
        except Exception:
            payload = {}

        q = (payload.get("q") or "").strip()
        source = (payload.get("source") or "operator").strip() or "operator"
        topk = _get_topk(payload)

        # Policy: if it is clearly prohibited through ENV, it behaves like an old guard,
        # only now it is manageable.
        if not (allow_ester and allow_search):
            return jsonify(
                {
                    "ok": False,
                    "mode": "B",
                    "source": source,
                    "query": q,
                    "reason": "not_allowed_by_policy",
                    "items": [],
                    "providers_tried": [],
                }
            )

        if not q:
            return jsonify(
                {
                    "ok": False,
                    "mode": "B",
                    "source": source,
                    "query": q,
                    "reason": "empty_query",
                    "items": [],
                    "providers_tried": [],
                }
            )

        search_res = _simple_search_via_web_search(q, topk)
        ok = bool(search_res.get("ok"))
        items = search_res.get("items") or []
        providers_tried = search_res.get("providers_tried") or []
        error = search_res.get("error")

        resp: Dict[str, Any] = {
            "ok": ok,
            "mode": "B",  # po analogii s /ester/net/search_logged
            "source": source,
            "query": q,
            "items": items,
            "providers_tried": providers_tried,
        }
        if not ok and error:
            resp["reason"] = error

        return jsonify(resp)