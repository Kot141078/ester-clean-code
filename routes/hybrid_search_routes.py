# -*- coding: utf-8 -*-
"""
routes/hybrid_search_routes.py - REST i metriki dlya gibrid-retrivera.

Endpointy:
  • POST /search/hybrid {"q":"...","k":8,"scope":{...}}
  • GET  /metrics/hybrid_search

Mosty:
- Yavnyy: (Poisk ↔ Memory) edinaya tochka vkhoda dlya vsekh klientov (v t.ch. Video QA).
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) RRF i normirovka v odnom meste.
- Skrytyy #2: (UX ↔ Sovmestimost) kontrakty «kak vezde»: {"ok","mode","items"}.

Zemnoy abzats:
Eto «dispetcher poiska»: daesh zapros - poluchaesh luchshie kusochki, nezavisimo ot togo, gde oni lezhat.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hybrid = Blueprint("hybrid_search", __name__)

try:
    from modules.search.hybrid_retriever import hybrid_search, counters  # type: ignore
except Exception:  # pragma: no cover
    hybrid_search = counters = None  # type: ignore


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp_hybrid)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


@bp_hybrid.route("/search/hybrid", methods=["POST"])
def api_hybrid():
    """Edinaya tochka vkhoda gibridnogo poiska."""
    if hybrid_search is None:
        return jsonify({"ok": False, "error": "hybrid retriever unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "q is required"}), 400
    try:
        k = int(data.get("k", 8))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "k must be integer"}), 400
    scope = data.get("scope") or None
    try:
        res = hybrid_search(q=q, k=k, scope=scope)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_hybrid.route("/metrics/hybrid_search", methods=["GET"])
def metrics():
    """Prometheus-metriki po retriveru (text/plain)."""
    if counters is None:
        text = "hybrid_calls_total 0\nhybrid_sparse_hits 0\nhybrid_dense_hits 0\n"
        return (text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
    try:
        c = counters()
    except Exception as e:
        text = f"# error {e}\nhybrid_calls_total 0\nhybrid_sparse_hits 0\nhybrid_dense_hits 0\n"
        return (text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
    text = (
        f"hybrid_calls_total {c.get('calls_total', 0)}\n"
        f"hybrid_sparse_hits {c.get('sparse_hits', 0)}\n"
        f"hybrid_dense_hits {c.get('dense_hits', 0)}\n"
    )
    return (text, 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


__all__ = ["bp_hybrid", "register", "init_app"]