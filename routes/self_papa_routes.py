# -*- coding: utf-8 -*-
"""
routes/self_papa_routes.py - REST dlya profilea/otpechatkov/zapisi v pamyat i lokatora Papy.

Mosty:
- Yavnyy: (Memory ↔ Samoidentifikatsiya) vydaem profile i kladem ego v pamyat.
- Skrytyy #1: (Poisk ↔ Set) lokalnyy i P2P-poisk s uvazheniem privatnosti (tolko patterny/kheshi).
- Skrytyy #2: (Prioritet ↔ Kontrol) sluzhit istochnikom pravdy dlya drugikh moduley.

Zemnoy abzats:
Eto «lichnaya kartochka Papy» i «poiskovik svoikh». Bez lishnego shuma - rovno to, chto nuzhno.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_papa = Blueprint("self_papa", __name__)

try:
    from modules.self.papa_passport import papa_passport, papa_fingerprint, affirm  # type: ignore
    from modules.self.papa_locator import search_local, search_p2p  # type: ignore
except Exception:
    papa_passport = papa_fingerprint = affirm = None  # type: ignore
    search_local = search_p2p = None  # type: ignore

def register(app):
    app.register_blueprint(bp_papa)

@bp_papa.route("/self/papa/passport", methods=["GET"])
def api_passport():
    if papa_passport is None: return jsonify({"ok": False, "error":"papa_passport unavailable"}), 500
    return jsonify({"ok": True, **papa_passport()})

@bp_papa.route("/self/papa/fingerprint", methods=["GET"])
def api_fp():
    if papa_fingerprint is None: return jsonify({"ok": False, "error":"papa_passport unavailable"}), 500
    return jsonify(papa_fingerprint())

@bp_papa.route("/self/papa/affirm", methods=["POST"])
def api_affirm():
    if affirm is None: return jsonify({"ok": False, "error":"papa_passport unavailable"}), 500
    return jsonify(affirm())

@bp_papa.route("/self/papa/locate", methods=["GET"])
def api_loc_local():
    if search_local is None: return jsonify({"ok": False, "error":"papa_locator unavailable"}), 500
    q = request.args.get("q","").strip() or None
    return jsonify(search_local(q=q))

@bp_papa.route("/self/papa/locate/global", methods=["POST"])
def api_loc_p2p():
    if search_p2p is None: return jsonify({"ok": False, "error":"papa_locator unavailable"}), 500
    d = (request.get_json(True, True) or {})
    q = str(d.get("q","")).strip() or None
    return jsonify(search_p2p(q=q))
# c=a+b