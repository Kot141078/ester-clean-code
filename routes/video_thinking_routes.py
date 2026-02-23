# -*- coding: utf-8 -*-
"""
routes/video_thinking_routes.py — «kryuchki» dlya myslitelnogo konveyera:
  - POST /thinking/video/autosearch {topic, limit?} v†' ytsearch + ingest
  - GET  /thinking/video/rules/example v†' JSON-shablon pravila

Mosty:
- Yavnyy: (Myshlenie v†" Proaktiv) Thinking-payplayn poluchaet prostuyu HTTP-ruchku dlya zapuska video-poiska po teme.
- Skrytyy #1: (Infoteoriya v†" Memory) R ezultaty idut cherez ingest yadro Re skladyvayutsya v pamyat/KG, dostupny dlya RAG.
- Skrytyy #2: (Kibernetika v†" Kontrol) Bneshniy vyzov s limitami — reguliruem obem pritoka (norma reaktsii).

Zemnoy abzats:
Eto kak «pischalka» na paneli mozga: mysl voznikla — nazhali — master probezhal sklad, prines svezhie yaschiki (video-konspekty).

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.proactive.video_autorunner import run_once  # type: ignore
except Exception:
    run_once = None  # type: ignore

bp_thinking_video = Blueprint("thinking_video", __name__)

def _err(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code

@bp_thinking_video.route("/thinking/video/autosearch", methods=["POST"])
def thinking_autosearch():
    if run_once is None:
        return _err("autorunner not available", 500)
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        topic = (data.get("topic") or "").strip()
        limit = int(data.get("limit") or 3)
        if not topic:
            return _err("topic is required")
        rep = run_once(mode="search", topic=topic, limit=limit)
        return jsonify(rep)
    except Exception as e:
        return _err(f"exception: {e}", 500)

@bp_thinking_video.route("/thinking/video/rules/example", methods=["GET"])
def thinking_rules_example():
    """
    Primer pravila dlya thinking_pipeline (podklyuchi v suschestvuyuschiy dvizhok pravil):
    - Esli v soobschenii vstrechaetsya tema X — zapustit avtopoisk video po X (limit 2), zatem otdat kratkuyu vyzhimku.
    """
    rule = {
        "name": "video_autosearch_on_topic",
        "when": {"kind": "text_contains_topic", "min_len": 8},
        "actions": [
            {"kind": "http_post", "url": "/thinking/video/autosearch", "json": {"topic": "{{topic}}", "limit": 2}},
            {"kind": "summarize", "hint": "video"},
        ],
        "notes": "Podklyuchite v vash thinking_pipeline soglasno ego kontraktu pravil."
    }
    return jsonify({"ok": True, "rule": rule})

def register(app):
    """Podkhvatyvaetsya routes/register_all.py (drop-in)."""
# app.register_blueprint(bp_thinking_video)