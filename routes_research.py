# -*- coding: utf-8 -*-
"""Marshruty /research/search (GET/POST). Used Research Agent.

Ispravleniya/uluchsheniya:
- ubran BOM/musor (U+FEFF), vosstanovlena normalnaya UTF-8 stroka dokumentatsii;
- korrektnaya registratsiya blueprint cherez app.register_blueprint(..., url_prefix=...);
- edinyy parser parametrov (query/k) i myagkaya validatsiya;
- bezopasnyy vyzov agent.search() s avto-podborom podderzhivaemykh kwargs
  (chtoby ne lomat sovmestimost pri raznykh versiyakh ResearchAgent);
- obrabotka oshibok bez padeniya servera (HTTP 400/500).

Mosty:
- Yavnyy (Kibernetika ↔ API): odin nablyudaemyy vkhod (query) → izmerimyy vykhod (results + meta).
- Skrytyy 1 (Logika ↔ Nadezhnost): “myagkaya validatsiya” vmesto isklyucheniy na empty vvode.
- Skrytyy 2 (Infoteoriya ↔ Interfeys): parametr k ogranichivaet obem otveta (kanal/shum).

Zemnoy abzats:
Eto kak filtr na nasose: ty ne zastavlyaesh sistemu “zhevat” pustotu i musor. Porog k i
normalnaya obrabotka oshibok ekonomyat resursy i nervy, osobenno kogda zaprosy letyat
pachkami ot UI/agentov.

# c=a+b"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from research_agent import ResearchAgent
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _parse_query_and_k() -> Tuple[str, Optional[int]]:
    """
    Podderzhivaem:
    - GET: ?query=...&k=...
    - POST JSON: {"query": "...", "k": 10}
    """
    if request.method == "GET":
        q = (request.args.get("query", "") or "").strip()
        k_raw = (request.args.get("k", "") or "").strip()
    else:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        q = str(data.get("query") or "").strip()
        k_raw = str(data.get("k") or "").strip()

    k: Optional[int] = None
    if k_raw:
        try:
            k_int = int(k_raw)
            if k_int > 0:
                k = k_int
        except Exception:
            k = None

    return q, k


def _safe_agent_search(agent: ResearchAgent, query: str, **kwargs: Any) -> Any:
    """Call agent.search with automatic selection of quargs by signature.
    If ResearchAgent only accepts (queers), it quietly degrades."""
    try:
        sig = inspect.signature(agent.search)  # type: ignore[arg-type]
        accepted = set(sig.parameters.keys())
    except Exception:
        accepted = set()

    call_kwargs = {k: v for k, v in kwargs.items() if k in accepted}
    try:
        if call_kwargs:
            return agent.search(query, **call_kwargs)  # type: ignore[misc]
        return agent.search(query)  # type: ignore[misc]
    except TypeError:
        # Just in case: if the signature does not reflect reality (wrappers/decorators)
        return agent.search(query)  # type: ignore[misc]


def register_research_routes(app, vstore, memory_manager, url_prefix: str = "/research") -> Blueprint:
    """Registers a blueprint and returns it (convenient for tests).
    store/memory_manager is sent to agent.search if it knows how to accept them."""
    bp = Blueprint("research", __name__)
    agent = ResearchAgent()

    @bp.get("/search")
    @jwt_required()
    def research_search_get():
        q, k = _parse_query_and_k()
        if not q:
            return jsonify({"results": [], "meta": {"query": q, "k": k}}), 200
        try:
            results = _safe_agent_search(agent, q, k=k, vstore=vstore, memory_manager=memory_manager)
            return jsonify({"results": results, "meta": {"query": q, "k": k}}), 200
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"{e.__class__.__name__}: {e}", "meta": {"query": q, "k": k}}), 500

    @bp.post("/search")
    @jwt_required()
    def research_search_post():
        q, k = _parse_query_and_k()
        if not q:
            return jsonify({"results": [], "meta": {"query": q, "k": k}}), 200
        try:
            results = _safe_agent_search(agent, q, k=k, vstore=vstore, memory_manager=memory_manager)
            return jsonify({"results": results, "meta": {"query": q, "k": k}}), 200
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": f"{e.__class__.__name__}: {e}", "meta": {"query": q, "k": k}}), 500

    # Correct blueprint registration (without gluing url_prefix inside decorators)
    app.register_blueprint(bp, url_prefix=url_prefix)
    return bp