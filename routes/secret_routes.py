# -*- coding: utf-8 -*-
"""routes/secret_routes.py - REST dlya lokalnogo sekret-stora.

Mosty:
- Yavnyy: (Veb ↔ Sekrety) prostye operatsii nad sekretami.
- Skrytyy #1: (Audit ↔ Prozrachnost) yavno vozvraschaem statusy/oshibki.
- Skrytyy #2: (Kibernetika ↔ Vyzhivanie) unifikatsiya vmesto ENV.

Zemnoy abzats:
Kuda klast tokeny: syuda.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_sec = Blueprint("secret_routes", __name__)

try:
    from modules.resilience.secret_store import put as _put, get as _get, rotate as _rotate  # type: ignore
except Exception:
    _put = _get = _rotate = None  # type: ignore

def register(app):
    app.register_blueprint(bp_sec)

@bp_sec.route("/secret/list", methods=["GET"])
def api_list():
    import os, json
    from modules.resilience.secret_store import DIR as _DIR  # type: ignore
    items=[]
    if os.path.isdir(_DIR):
        for fn in os.listdir(_DIR):
            if fn.endswith(".sec.json"):
                items.append(fn[:-9])
    return jsonify({"ok": True, "items": items})

@bp_sec.route("/secret/put", methods=["POST"])
def api_put():
    if _put is None: return jsonify({"ok": False, "error":"secret store unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_put(str(d.get("name","")), str(d.get("value",""))))

@bp_sec.route("/secret/get", methods=["POST"])
def api_get():
    if _get is None: return jsonify({"ok": False, "error":"secret store unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_get(str(d.get("name",""))))

@bp_sec.route("/secret/rotate", methods=["POST"])
def api_rotate():
    if _rotate is None: return jsonify({"ok": False, "error":"secret store unavailable"}), 500
    return jsonify(_rotate())
# c=a+b