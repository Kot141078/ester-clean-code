# -*- coding: utf-8 -*-
"""routes/thinking_web_context_routes.py - REST dlya "rasshiritelya konteksta" + metrics + admin-UI.

Endpoint:
  • POST /thinking/web_context/expand {"q","k"?:5,"autofetch"?:false,"max_fetch"?:3}
  • GET /metrics/web_context
  • GET /admin/web_search - mini-panel proverki poiska/plana

Mosty:
- Yavnyy: (Myshlenie ↔ Vvod) agent mozhet sam dobirat istochniki i zagruzhat ikh v pamyat.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) best-effort vyzovy k /ingest/* bez izmeneniya ikh kontraktov.
- Skrytyy #2: (UX ↔ Prozrachnost) prostaya admin-stranitsa dlya ruchnoy proverki.
- Skrytyy #3: (Inzheneriya ↔ Kontrakty) determinirovannye JSON-otvety i Prometheus-metriki.

Zemnoy abzats:
Eto “panel avtopodkormki”: zadal temu - sistema nashla istochniki i (esli razresheno) sama podvezla ikh v konveyer.
Prostye vkhody/vykhody, nichego lishnego - udobno dlya payplaynov i UI.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request, render_template, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_wc = Blueprint("web_context", __name__, template_folder="../templates", static_folder="../static")

# Soft import expander
try:  # pragma: no cover
    from modules.thinking.web_context_expander import expand, counters  # type: ignore
except Exception:  # pragma: no cover
    expand = counters = None  # type: ignore


def register(app):  # pragma: no cover
    app.register_blueprint(bp_wc)


def init_app(app):  # pragma: no cover
    register(app)


@bp_wc.post("/thinking/web_context/expand")
def api_expand():
    """Expand the query with sources and (optionally) autoload into memory."""
    if expand is None:
        return jsonify({"ok": False, "error": "web_context_expander_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    q = (data.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "q is required"}), 400
    try:
        k = int(data.get("k") or 5)
    except Exception:
        k = 5
    try:
        max_fetch = int(data.get("max_fetch") or 3)
    except Exception:
        max_fetch = 3
    k = max(1, min(k, 25))
    max_fetch = max(0, min(max_fetch, 10))
    autofetch = bool(data.get("autofetch", False))
    try:
        rep = expand(q=q, k=k, autofetch=autofetch, max_fetch=max_fetch)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_wc.get("/metrics/web_context")
def metrics():
    """Prometheus metrics for context expander performance."""
    if counters is None:
        body = (
            "web_context_expand_calls 0\n"
            "web_context_autofetch_jobs 0\n"
            "web_context_autofetch_ok 0\n"
            "web_context_autofetch_fail 0\n"
        )
        return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
    try:
        c = counters()  # type: ignore[misc]
    except Exception:
        c = {}
    body = (
        f"web_context_expand_calls {c.get('expand_calls', 0)}\n"
        f"web_context_autofetch_jobs {c.get('autofetch_jobs', 0)}\n"
        f"web_context_autofetch_ok {c.get('autofetch_ok', 0)}\n"
        f"web_context_autofetch_fail {c.get('autofetch_fail', 0)}\n"
    )
    return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


@bp_wc.get("/admin/web_search")
def admin_web_search():
    """Mini-panel for manual search/load plan verification."""
    return render_template("admin_web_search.html")


__all__ = ["bp_wc", "register", "init_app"]
# c=a+b