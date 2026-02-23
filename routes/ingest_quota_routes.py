# -*- coding: utf-8 -*-
"""
routes/ingest_quota_routes.py - REST: status/spisanie/penalize dlya ingest-baketov.

Mosty:
- Yavnyy: (Veb ↔ Kvoty) tsentralizovannyy kontrol nagruzki.
- Skrytyy #1: (MediaMind ↔ Spravedlivost) media.watch/ingest mogut proveryat kvoty.
- Skrytyy #2: (Planirovschik ↔ Metriki) udoben dlya grafikov.

Zemnoy abzats:
Smotrim, u kogo skolko «topliva», i vydaem po norme.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ingest_quota_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.ingest.backpressure import status as _st, consume as _cons, penalize as _pen  # type: ignore
except Exception:
    _st=_cons=_pen=None  # type: ignore

@bp.route("/ingest/quota/status", methods=["GET"])
def api_st():
    if _st is None: return jsonify({"ok": False, "error":"quota_unavailable"}), 500
    return jsonify(_st())

@bp.route("/ingest/quota/consume", methods=["POST"])
def api_cons():
    if _cons is None: return jsonify({"ok": False, "error":"quota_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_cons(str(d.get("source","unknown")), float(d.get("cost",1.0))))

@bp.route("/ingest/quota/penalize", methods=["POST"])
def api_pen():
    if _pen is None: return jsonify({"ok": False, "error":"quota_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_pen(str(d.get("source","unknown")), int(d.get("seconds",30))))
# c=a+b