# -*- coding: utf-8 -*-
"""
modules/net_bridge.py
SerpApi-backed search bridge with strict offline gate.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib import parse as urlparse
from urllib import request as urlrequest

from modules.net_guard import allow_network, deny_payload


_SERP_ENDPOINT = "https://serpapi.com/search.json"


def _serpapi_key() -> str:
    return (os.getenv("SERPAPI_KEY") or "").strip()


def _normalize_items(data: Dict[str, Any], limit: int) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    kg = data.get("knowledge_graph")
    if isinstance(kg, dict):
        out.append(
            {
                "title": str(kg.get("title") or "Info"),
                "link": str(kg.get("website") or ""),
                "snippet": str(kg.get("description") or ""),
            }
        )

    for item in data.get("organic_results") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or ""),
                "link": str(item.get("link") or ""),
                "snippet": str(item.get("snippet") or ""),
            }
        )
        if len(out) >= limit:
            break

    return out[:limit]


def _serpapi_search(query: str, limit: int = 5) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"ok": False, "error": "no_query"}

    key = _serpapi_key()
    if not key:
        return {
            "ok": False,
            "error": "missing_serpapi_key",
            "hint": "Set SERPAPI_KEY to enable external search.",
        }

    if not allow_network(_SERP_ENDPOINT):
        return deny_payload(_SERP_ENDPOINT, target="serpapi")

    params = {
        "engine": "google",
        "q": q,
        "api_key": key,
        "num": max(1, min(int(limit or 5), 10)),
    }
    url = _SERP_ENDPOINT + "?" + urlparse.urlencode(params)

    req = urlrequest.Request(url, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:  # nosec B310 (guarded above)
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": "serpapi_request_failed", "detail": str(e)}

    try:
        data = json.loads(raw)
    except Exception as e:
        return {"ok": False, "error": "serpapi_invalid_json", "detail": str(e)}

    items = _normalize_items(data, max(1, min(int(limit or 5), 10)))
    return {"ok": True, "results": items, "count": len(items), "engine": "serpapi"}


def google_search(query: str, limit: int = 5) -> List[Dict[str, str]]:
    rep = _serpapi_search(query, limit)
    if not rep.get("ok"):
        return []
    return list(rep.get("results") or [])


def search(payload: Dict[str, Any]) -> Dict[str, Any]:
    q = str((payload or {}).get("q") or "").strip()
    limit = int((payload or {}).get("limit") or (payload or {}).get("num") or 5)
    return _serpapi_search(q, limit)
