# -*- coding: utf-8 -*-
"""routes/crawl_policy_routes.py - REST dlya lokalnoy politiki kroulinga.

Mosty:
- Yavnyy: (Veb ↔ Krouling) bystraya proverka pered zagruzkoy.
- Skrytyy #1: (Zakonnost ↔ Kontrol) edinaya tochka prinyatiya resheniya.
- Skrytyy #2: (Avtonomiya ↔ Vezhlivost) uvazhenie zaderzhek/litsenziy.

Zemnoy abzats:
Asked - “mozhno/nelzya” i kak akkuratno - i poshli.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_crawl = Blueprint("crawl_policy", __name__)

try:
    from modules.crawl.policy import check as _check  # type: ignore
except Exception:
    _check = None  # type: ignore

def register(app):
    app.register_blueprint(bp_crawl)

@bp_crawl.route("/crawler/policy/check", methods=["POST"])
def api_check():
    if _check is None: return jsonify({"ok": False, "error":"crawl policy unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_check(str(d.get("url","")), str(d.get("purpose","research"))))
# c=a+b