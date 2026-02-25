# -*- coding: utf-8 -*-
from __future__ import annotations
"""routes/rag_status_routes.py - status RAG s myagkim rezhimom.

Ruchka:
  • GET /rag/status → {"ok":bool,"hybrid_available":bool,"soft":bool,"notes":[...]}
Code answer:
  • 200 — esli gibrid dostupen ILI vklyuchen myagkiy rezhim (ENV RAG_STATUS_SOFT=1)
  • 500 — esli hybrid nedostupen i myagkiy rezhim vyklyuchen

MOSTY:
- Yavnyy: Diagnostika RAG ↔ Web (stabilnaya proverka bez POST tel).
- Skrytyy #1: Observability ↔ CI (precheck dlya payplaynov).
- Skrytyy #2: ENV ↔ Povedenie (pereklyuchenie 200/500 cherez RAG_STATUS_SOFT).

ZEMNOY ABZATs (inzheneriya):
Statusnaya ruchka ne izmenyaet suschestvuyuschie kontrakty RAG. Ona lish soobschaet
gotovnost podsistemy. "Soft mode" nuzhen, why not padali smoke‑testy
na stendakh bez vektornogo indeksa.
# c=a+b"""
import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rag_status_bp", __name__)

try:
    from modules.rag.hybrid import hybrid_search as _hyb  # type: ignore
except Exception:
    _hyb = None  # type: ignore

@bp.get("/rag/status")
def rag_status():
    notes = []
    hybrid_ok = _hyb is not None
    soft = os.getenv("RAG_STATUS_SOFT", "").strip() in ("1", "true", "yes", "on")
    if not hybrid_ok:
        notes.append("modules.rag.hybrid.hybrid_search not available")
    if os.getenv("PERSIST_DIR"):
        notes.append("PERSIST_DIR set")
    if os.getenv("COLLECTION_NAME"):
        notes.append("COLLECTION_NAME set")
    body = {
        "ok": bool(hybrid_ok),
        "hybrid_available": bool(hybrid_ok),
        "soft": bool(soft),
        "notes": notes,
    }
    status = 200 if (hybrid_ok or soft) else 500
    return jsonify(body), status

def register(app):  # pragma: no cover
    app.register_blueprint(bp)

__all__ = ["bp", "register"]
# c=a+b