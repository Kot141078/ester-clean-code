# -*- coding: utf-8 -*-
"""routes/outreach_routes.py - REST: /outreach/proposal/* (generate/get)

Mosty:
- Yavnyy: (Veb ↔ Outreach) generatsiya MD/HTML i pisma.
- Skrytyy #1: (Portfolio ↔ Ssylki) na stranitse portfolio est ankory k kartochkam.
- Skrytyy #2: (Passport/RAG ↔ Prozrachnost/Poisk) vydachi logiruyutsya i indeksiruyutsya.

Zemnoy abzats:
Nazhal - i gotovo predlozhenie i chernovik pisma, kotorye mozhno srazu otpravlyat.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, send_file
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("outreach_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.outreach.proposal import generate as _gen, get_path as _getp  # type: ignore
except Exception:
    _gen=_getp=None  # type: ignore

@bp.route("/outreach/proposal/generate", methods=["POST"])
def api_generate():
    if _gen is None: return jsonify({"ok": False, "error":"outreach_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_gen(str(d.get("opp_id","")), dict(d.get("extras") or {})))

@bp.route("/outreach/proposal/get", methods=["GET"])
def api_get():
    if _getp is None: return jsonify({"ok": False, "error":"outreach_unavailable"}), 500
    oid=str(request.args.get("id","")); fmt=str(request.args.get("format","md"))
    rep=_getp(oid, fmt)
    if not rep.get("ok"): return jsonify(rep), 404
    mt="text/plain; charset=utf-8" if fmt!="html" else "text/html; charset=utf-8"
    return send_file(rep["path"], mimetype=mt)
# c=a+b