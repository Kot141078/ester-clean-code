# -*- coding: utf-8 -*-
"""
routes/hypothesis_routes.py - REST-endpointy dlya HypothesisStore («sny», idei).

Marshruty:
  POST /hypothesis/add           - dobavit gipotezu
  GET  /hypothesis/list          - poluchit spisok gipotez (po teme/limitu)
  POST /hypothesis/feedback      - otmetit ispolzovanie/podpravit score

Sovmestimost:
  • Flask Blueprint s register_hypothesis_routes(app)
  • Ne trogaet suschestvuyuschie puti/routy; avtonomnyy blyuprint.
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from memory.hypothesis_store import HypothesisStore  # drop-in
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

hypothesis_bp = Blueprint("hypothesis", __name__, url_prefix="/hypothesis")
_hs = HypothesisStore()


@hypothesis_bp.post("/add")
def hypothesis_add():
    """
    Telo JSON:
      {
        "text": "ideya...",
        "topic": "topic::memory",
        "tags": ["dreams","cluster"] | "dreams, cluster",
        "score": 0.6
      }
    Otvet: {"ok": True, "id": "..."}
    """
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return jsonify({"ok": False, "error": "text is required"}), 400
        topic = str(data.get("topic") or "")
        tags_in = data.get("tags") or []
        if isinstance(tags_in, str):
            tags: List[str] = [t.strip() for t in tags_in.split(",") if t.strip()]
        else:
            tags = list(tags_in)
        score = float(data.get("score") or 0.5)
        hid = _hs.add(text=text, topic=topic, tags=tags, score=score)
        return jsonify({"ok": True, "id": hid})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@hypothesis_bp.get("/list")
def hypothesis_list():
    """
    Parametry:
      ?topic=topic::memory&limit=50
    """
    try:
        topic = request.args.get("topic") or None
        limit = int(request.args.get("limit", "100"))
        items = _hs.list(topic=topic, limit=limit)
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@hypothesis_bp.post("/feedback")
def hypothesis_feedback():
    """
    Telo JSON:
      { "id": "<hid>", "used": true, "delta_score": +0.2 }
    """
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        hid = str(data.get("id") or "")
        if not hid:
            return jsonify({"ok": False, "error": "id is required"}), 400
        used = data.get("used")
        delta = data.get("delta_score")
        res = _hs.feedback(hid=hid, used=used, delta_score=delta)
        code = 200 if (isinstance(res, dict) and res.get("ok")) else 404
        return jsonify(res), code
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


def register_hypothesis_routes(app) -> None:  # pragma: no cover
    """Sovmestimaya registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(hypothesis_bp)


# Unifitsirovannye khuki po konventsii proekta
def register(app):  # pragma: no cover
    app.register_blueprint(hypothesis_bp)


def init_app(app):  # pragma: no cover
    app.register_blueprint(hypothesis_bp)


__all__ = ["hypothesis_bp", "register_hypothesis_routes", "register", "init_app"]