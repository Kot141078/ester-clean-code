# -*- coding: utf-8 -*-
"""
routes/providers_probe.py - status provayderov LLM.

MOSTY:
- (Yavnyy) GET /providers/status - tekuschiy vybrannyy provayder i bazovye proverki.
- (Skrytyy #1) Probuem LM Studio (OpenAI-sovmestimyy /v1/models) na dostupnost.
- (Skrytyy #2) Vozvraschaem kompaktnyy otchet dlya UI, ne trebuyuschiy vneshnego interneta.

ZEMNOY ABZATs:
Kak panel lampochek: vidno, kakaya «mozgovaya korobka» seychas aktivna i zhiva li «lokalnaya».

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify
from modules.providers.registry import select_provider
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_probe", __name__, url_prefix="/providers")

def register(app):
    app.register_blueprint(bp)

def _probe_lmstudio() -> bool:
    try:
        import requests  # type: ignore
        url = (os.getenv("LMSTUDIO_ENDPOINTS","http://127.0.0.1:1234").split(";")[0].rstrip("/")
               + "/v1/models")
        r = requests.get(url, timeout=2)
        return r.status_code in (200, 401, 403)
    except Exception:
        return False

@bp.get("/status")
def status():
    p = select_provider(None)
    return jsonify({
        "ok": True,
        "active_provider": p.get("name"),
        "lmstudio_probe": _probe_lmstudio(),
        "authoring_backend": (os.getenv("AUTHORING_LLM_BACKEND","local")),
    })
# c=a+b