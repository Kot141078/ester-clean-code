# -*- coding: utf-8 -*-
"""
routes/social_ledger_routes.py - REST: zhurnal publikatsiy.

Mosty:
- Yavnyy: (Veb ↔ Uchet) otdaet lentu publikatsiy dlya interfeysa/otchetov.
- Skrytyy #1: (RBAC ↔ Ostorozhnost) chtenie otkrytoe; modifikatsiya idet tolko cherez uploaders.
- Skrytyy #2: (Memory ↔ Profile) istochniki uzhe otrazheny.

Zemnoy abzats:
Kak otkryt bukhgalterskuyu knigu na nuzhnoy stranitse i uvidet vse zapisi.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("social_ledger_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.social.ledger import list_posts as _list  # type: ignore
except Exception:
    _list=None  # type: ignore

@bp.route("/social/ledger/list", methods=["GET"])
def api_ledger_list():
    if _list is None: return jsonify({"ok": False, "error":"ledger_unavailable"}), 500
    return jsonify(_list())
# c=a+b