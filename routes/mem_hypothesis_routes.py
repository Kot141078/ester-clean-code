# -*- coding: utf-8 -*-
"""
routes/mem_hypothesis_routes.py - aliasy HypothesisStore pod /mem/hypothesis (sovmestimo s openapi.yaml).

Marshruty:
  POST /mem/hypothesis/add
  GET  /mem/hypothesis/list
  POST /mem/hypothesis/feedback

Mosty:
- Yavnyy: (Memory ↔ Veb) edinye REST-ruchki dlya zapisi/poiska «gipotez».
- Skrytyy #1: (Infoteoriya ↔ Ekonomiya) score kak aprior snizhaet shum vyborki.
- Skrytyy #2: (Logika ↔ Kontrakty) strogaya validatsiya vkhoda i kody oshibok.

Zemnoy abzats:
Eto «chernovik idey»: dobavil mysl → ona sokhranilas v HypothesisStore; pozzhe mozhno vybrat po teme,
podnyat/opustit ves cherez feedback i otfiltrovat vazhnoe.

c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

from memory.hypothesis_store import HypothesisStore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

mem_hypo_bp = Blueprint("mem_hypothesis", __name__, url_prefix="/mem/hypothesis")
_HS: Optional[HypothesisStore] = None
_HS_PATH: Optional[str] = None


def _persist_dir() -> str:
    base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    return base


def _get_hs() -> HypothesisStore:
    global _HS, _HS_PATH
    path = os.path.join(_persist_dir(), "hypothesis.jsonl")
    if _HS is None or _HS_PATH != path:
        _HS = HypothesisStore(path=path)
        _HS_PATH = path
    return _HS


@mem_hypo_bp.post("/add")
@jwt_required()
def mem_hypothesis_add():
    """Dobavit gipotezu."""
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        text = str((data.get("text") or "")).strip()
        if not text:
            return jsonify({"ok": False, "error": "text is required"}), 400
        topic = str(data.get("topic") or "")
        tags_in = data.get("tags") or []
        if isinstance(tags_in, str):
            tags: List[str] = [t.strip() for t in tags_in.split(",") if t.strip()]
        else:
            tags = list(tags_in)
        score = float(data.get("score") or 0.5)
        hid = _get_hs().add(text=text, topic=topic, tags=tags, score=score)
        return jsonify({"ok": True, "id": hid})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@mem_hypo_bp.get("/list")
@jwt_required()
def mem_hypothesis_list():
    """Poluchit spisok gipotez po teme/limitu."""
    try:
        topic = request.args.get("topic") or None
        limit = int(request.args.get("limit", "100"))
        items = _get_hs().list(topic=topic, limit=limit)
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@mem_hypo_bp.post("/feedback")
@jwt_required()
def mem_hypothesis_feedback():
    """Otmetit ispolzovanie/izmenit score gipotezy."""
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        hid = str((data.get("id") or "")).strip()
        if not hid:
            return jsonify({"ok": False, "error": "id is required"}), 400
        used = data.get("used")
        delta = data.get("delta_score")
        res = _get_hs().feedback(hid=hid, used=used, delta_score=delta)
        code = 200 if (isinstance(res, dict) and res.get("ok")) else 404
        return jsonify(res), code
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


def register_mem_hypothesis_routes(app) -> None:  # pragma: no cover
    """Sovmestimaya registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(mem_hypo_bp)


# Unifitsirovannye khuki po konventsii proekta
def register(app):  # pragma: no cover
    app.register_blueprint(mem_hypo_bp)


def init_app(app):  # pragma: no cover
    app.register_blueprint(mem_hypo_bp)


__all__ = ["mem_hypo_bp", "register_mem_hypothesis_routes", "register", "init_app"]
