# -*- coding: utf-8 -*-
"""
routes/web_search_routes.py - REST-obertka nad modules.web_search.search_web + metriki.

Endpointy:
  • POST /search/web {"q":"...","k"?:5} → {"ok":true,"items":[{title,url,snippet,source}]}
  • GET  /metrics/web_search

Mosty:
- Yavnyy: (Poisk ↔ Ingest) REST-servis otdaet URL, kotorye srazu mozhno peredat v suschestvuyuschiy konveyer zagruzki.
- Skrytyy #1: (Infoteoriya ↔ RAG) naydennye dokumenty usilivayut posleduyuschie otvety.
- Skrytyy #2: (UX ↔ Volya) etot zhe endpoint vyzyvaetsya agentom «po svoey vole» iz thinking-patterna.

Zemnoy abzats (anatomiya/inzheneriya):
Eto «knopka nayti»: poluchaet zapros, vozvraschaet ssylki i kratkie snippety. Vykhod determinirovannyy i
podkhodit dlya payplaynov - mozhno tut zhe otpravit rezultaty v ingest i pamyat.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_web_search = Blueprint("web_search", __name__)

# Myagkiy import poiskovogo backend'a
try:  # pragma: no cover
    from modules.web_search import search_web  # type: ignore
except Exception:  # pragma: no cover
    search_web = None  # type: ignore

# Prosteyshie schetchiki
_CNT = {"calls_total": 0, "hits_total": 0}


def register(app):  # pragma: no cover
    app.register_blueprint(bp_web_search)


def init_app(app):  # pragma: no cover
    register(app)


@bp_web_search.post("/search/web")
def api_search_web():
    """Poisk po vebu. Vozvraschaet normalizovannye rezultaty dlya RAG/ingest."""
    if search_web is None:
        return jsonify({"ok": False, "error": "web_search module unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()
    try:
        k = int(data.get("k") or 5)
    except Exception:
        k = 5
    k = max(1, min(k, 25))
    if not q:
        return jsonify({"ok": False, "error": "q is required"}), 400
    try:
        items: List[Dict[str, Any]] = search_web(q, topk=k) or []  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    _CNT["calls_total"] += 1
    _CNT["hits_total"] += len(items)
    return jsonify({"ok": True, "items": items})


@bp_web_search.get("/metrics/web_search")
def metrics_web_search():
    """Prometheus-tekst s prostymi schetchikami vyzovov/rezultatov."""
    body = (
        f"web_search_calls_total {_CNT['calls_total']}\n"
        f"web_search_hits_total {_CNT['hits_total']}\n"
    )
    return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


__all__ = ["bp_web_search", "register", "init_app"]
# c=a+b