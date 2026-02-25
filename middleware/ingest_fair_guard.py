# -*- coding: utf-8 -*-
"""middleware/ingest_fair_guard.py - before_request-okhrannik dlya ogranicheniy ingest.

Mosty:
- Yavnyy: (Marshruty ↔ Ogranichenie) perekhvatyvaet /ingest/submit, primenyaet token-bucket.
- Skrytyy #1: (Nablyudaemost ↔ Vozvrat) pishet Retry-After pri 429.
- Skrytyy #2: (Gibkost ↔ Istochnik) istochnik berem iz X-Source ili IP.

Zemnoy abzats:
Zdes “shveytsar”: puskaet ne vsekh i ne srazu, chtoby zal ne zakhlebnulsya.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ingest_guard = Blueprint("ingest_fair_guard", __name__)

try:
    from modules.ingest.fair import admit as _admit  # type: ignore
except Exception:
    _admit = None  # type: ignore

TARGETS = ["/ingest/submit"]

def register(app):
    app.register_blueprint(bp_ingest_guard)

@bp_ingest_guard.before_app_request
def guard():
    if _admit is None: return None
    p = (request.path or "").split("?")[0]
    if p not in TARGETS: return None
    source = request.headers.get("X-Source") or request.remote_addr or "default"
    rep = _admit(source)
    if not rep.get("allow", True):
        resp = jsonify({"ok": False, "error": "rate_limited", "detail": rep})
        resp.status_code = 429
        ra = rep.get("retry_after", 1.0)
        resp.headers["Retry-After"] = f"{int(ra)}"
        return resp
    return None
# c=a+b