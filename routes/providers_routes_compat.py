# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, urllib.request
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_routes_compat", __name__)

def _oai_base() -> str | None:
    return os.environ.get("OPENAI_API_BASE") or os.environ.get("LMSTUDIO_URL")

def _probe_models(url: str | None) -> bool:
    if not url:
        return False
    try:
        req = urllib.request.Request(url.rstrip("/") + "/models", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as r:  # noqa: S310
            return 200 <= getattr(r, "status", 200) < 500
    except Exception:
        return False

@bp.get("/providers/status")
def providers_status():
    base = _oai_base()
    return jsonify({
        "ok": True,
        "active_provider": "lmstudio",
        "lmstudio_probe": _probe_models(base),
        "authoring_backend": "local",
    })

# sovmestimost: prostaya «karta» provayderov
@bp.get("/providers")
def providers_list():
    base = _oai_base()
    return jsonify({
        "ok": True,
        "items": [
            {"id": "lmstudio", "type": "openai-compatible", "base_url": base or ""},
        ]
    })