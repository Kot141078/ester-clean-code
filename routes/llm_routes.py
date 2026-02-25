# -*- coding: utf-8 -*-
"""routes/llm_routes.py - REST dlya brokera LLM: /llm/providers, /llm/complete.

Mosty:
- Yavnyy: (Veb ↔ Modeli) unifitsirovannyy HTTP-dostup k lokalnym/oblachnym LLM.
- Skrytyy #1: (Ekonomika ↔ CostFence) broker uzhe ogranichivaet byudzhet.
- Skrytyy #2: (Samorazvitie ↔ CodeSmith+) stabiliziruet zavisimosti dlya codesmith i pleybukov.

Zemnoy abzats:
One endpoint - raznye dvizhki: LM Studio, OpenAI-sovmestimye, Ollama.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_llm = Blueprint("llm_routes", __name__)

def register(app):
    app.register_blueprint(bp_llm)

@bp_llm.route("/llm/providers", methods=["GET"])
def api_providers():
    return jsonify({
        "ok": True,
        "default": (os.getenv("LLM_DEFAULT_PROVIDER","lmstudio") or "lmstudio").lower(),
        "lmstudio": os.getenv("LMSTUDIO_BASE_URL","http://127.0.0.1:1234/v1"),
        "ollama": os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434"),
        "openai_base": os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1"),
        "openai_enabled": bool(os.getenv("OPENAI_API_KEY","").strip())
    })

try:
    from modules.llm.broker import complete as _complete  # type: ignore
except Exception:
    _complete=None  # type: ignore

@bp_llm.route("/llm/complete", methods=["POST"])
def api_complete():
    if _complete is None: return jsonify({"ok": False, "error":"llm_broker_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_complete(
        str(d.get("provider","")),
        str(d.get("model","")),
        str(d.get("prompt","")),
        int(d.get("max_tokens",256)),
        float(d.get("temperature",0.2))
    ))
# c=a+b