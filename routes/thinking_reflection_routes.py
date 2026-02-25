# -*- coding: utf-8 -*-
"""routes/thinking_reflection_routes.py - HTTP-ruchki dlya affect-aware ocheredi refleksii.

Endpoint:
  • POST /thinking/reflection/enqueue {"item":{...}} → {"ok":true,"score":...,"size":...}
  • POST /thinking/reflection/pop {"n":1} → {"ok":true,"items":[{"id",...,"_score":...}]}
  • GET /metrics/reflection_affect → Prometheus text 0.0.4

Mosty:
- Yavnyy: (Memory ↔ Myshlenie) pozvolyaet RuleHub pinat refleksiyu po prioritetu.
- Skrytyy #1: (Infoteoriya ↔ Nablyudaemost) metriki ocheredi dostupny iz Prometheus.
- Skrytyy #2: (UX ↔ Control) prostoy REST bez izmeneniya suschestvuyuschikh payplaynov.

Zemnoy abzats (inzheneriya/anatomiya):
This is “ruchka upravleniya ocheredyu”: mozhno podat kartochku s emotsiyami i zabrat top-N na obdumyvanie.
Prostaya trubka: vkhod - JSON, vykhod - determinirovannyy otvet/metriki, nichego lishnego.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_reflect = Blueprint("reflect_affect", __name__)

# Soft import of queue core
try:  # pragma: no cover
    from modules.thinking.affect_reflection import enqueue as _enqueue, pop as _pop  # type: ignore
    # just to check the import:
    from modules.thinking.affect_reflection import score_item as _score_item  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    _enqueue = _pop = None  # type: ignore

QSTATE: Dict[str, int] = {"enqueued_total": 0, "popped_total": 0}


def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp_reflect)


def init_app(app) -> None:  # pragma: no cover
    register(app)


@bp_reflect.post("/thinking/reflection/enqueue")
def api_enqueue():
    """Place an element in the reflection queue (affect-aware)."""
    if _enqueue is None:
        return jsonify({"ok": False, "error": "affect_queue_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    item = dict(data.get("item") or {})
    try:
        rep = _enqueue(item)  # type: ignore[misc]
        # We are waiting for the dictionary; if not - leads
        if not isinstance(rep, dict):
            rep = {"ok": True, "result": rep}
        rep.setdefault("ok", True)
        QSTATE["enqueued_total"] += 1
        return jsonify(rep)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_reflect.post("/thinking/reflection/pop")
def api_pop():
    """Take the N best elements from the reflection queue."""
    if _pop is None:
        return jsonify({"ok": False, "error": "affect_queue_unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        n = int(data.get("n") or 1)
    except Exception:
        n = 1
    n = max(1, min(n, 100))
    try:
        items: List[Dict[str, Any]] = _pop(n)  # type: ignore[misc]
        QSTATE["popped_total"] += len(items)
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_reflect.get("/metrics/reflection_affect")
def metrics():
    """Promethneus text with current queue counters."""
    body = (
        f"reflection_affect_enqueued_total {QSTATE['enqueued_total']}\n"
        f"reflection_affect_popped_total {QSTATE['popped_total']}\n"
    )
    return Response(body, headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})


__all__ = ["bp_reflect", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp_reflect)
    return app