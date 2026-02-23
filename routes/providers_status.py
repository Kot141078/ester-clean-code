# -*- coding: utf-8 -*-
"""
routes/providers_status.py - status provayderov/SDK.

MOSTY:
- (Yavnyy) GET /providers/status - perechislyaet nalichie moduley i endpoints LM Studio.
- (Skrytyy #1) Ne padaet, esli paketov net - prosto false.
- (Skrytyy #2) Udobno dlya portala i self-check.

ZEMNOY ABZATs:
Kak «indikator lampochek»: vidno, kakie dvizhki gotovy k rabote.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_status", __name__, url_prefix="/providers")

def register(app):
    app.register_blueprint(bp)

def _has(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False

@bp.get("/status")
def status():
    lm_eps = (os.getenv("LMSTUDIO_ENDPOINTS") or "").split(";")
    return jsonify({
        "ok": True,
        "installed": {
            "openai": _has("openai"),
            "google-generativeai": _has("google.generativeai"),
            "xai": _has("xai"),  # esli budet ustanovlen paket
            "googleapiclient": _has("googleapiclient"),
            "requests": _has("requests"),
        },
        "lmstudio": {"endpoints": [e for e in lm_eps if e.strip()]}
    })
# c=a+b