# -*- coding: utf-8 -*-
"""routes/llm_broker_routes.py - REST: broker LLM (LM Studio / OpenAI-sovmestimye / Gemini).

Mosty:
- Yavnyy: (Veb ↔ Myshlenie) edinyy endpoint dlya zaversheniy.
- Skrytyy #1: (Ekonomika ↔ CostFence) vneshnie modeli mozhno otsenivat i ogranichivat.
- Skrytyy #2: (Avtonomiya ↔ Volya) “volya” vybiraet provaydera iskhodya iz zadach.

Zemnoy abzats:
Odin API - mnogo dvizhkov. Lokalno bystro, v oblake - po mere neobkhodimosti.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_llm = Blueprint("llm_broker", __name__)

try:
    from modules.llm.broker import complete as _complete  # type: ignore
except Exception:
    _complete=None  # type: ignore

def register(app):
    app.register_blueprint(bp_llm)

@bp_llm.route("/llm/broker/complete", methods=["POST"])
def api_complete():
    if _complete is None: return jsonify({"ok": False, "error":"llm_broker_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_complete(str(d.get("provider","lmstudio")), str(d.get("model","")), str(d.get("prompt","")), int(d.get("max_tokens",256)), float(d.get("temperature",0.2))))
# c=a+b