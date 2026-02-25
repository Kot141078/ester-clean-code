# -*- coding: utf-8 -*-
"""routes/skillforge_routes.py - REST: kuznitsa (draft/test/apply).

Mosty:
- Yavnyy: (Veb ↔ Samorazvitie) sdelat modul - cherez quarantine i testy.
- Skrytyy #1: (Bezopasnost ↔ Kontrol) A/B, zapreschen vypusk pri B.
- Skrytyy #2: (Instrumenty ↔ Protsessy) svyazka s deployer.stage/approve uzhe nastroena v sisteme.

Zemnoy abzats:
Knopki “chernovik”, “verka”, “vypusk v staging”.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_forge = Blueprint("skillforge", __name__)

try:
    from modules.self.skillforge import draft as _draft, test as _test, apply as _apply  # type: ignore
except Exception:
    _draft = _test = _apply = None  # type: ignore

def register(app):
    app.register_blueprint(bp_forge)

@bp_forge.route("/self/forge/draft", methods=["POST"])
def api_draft():
    if _draft is None: return jsonify({"ok": False, "error":"skillforge unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_draft(str(d.get("path","")), str(d.get("rfc","")), str(d.get("kind","module")), d.get("content_b64")))

@bp_forge.route("/self/forge/test", methods=["POST"])
def api_test():
    if _test is None: return jsonify({"ok": False, "error":"skillforge unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_test(str(d.get("id",""))))

@bp_forge.route("/self/forge/apply", methods=["POST"])
def api_apply():
    if _apply is None: return jsonify({"ok": False, "error":"skillforge unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_apply(str(d.get("id","")), str(d.get("reason",""))))
# c=a+b