# -*- coding: utf-8 -*-
"""
/_where — pokazat, kakoy app.py zapuschen, puti shablonov i vse pravila.

Mosty:
- Yavnyy: HTTP ↔ runtime (vidim realnyy fayl i konfiguratsiyu).
- Skrytye: (Marshruty ↔ Otladka), (Jinja ↔ FS).

Zemnoy abzats:
Eto «tablichka v elektroschite»: k kakoy linii podklyuchena panel pryamo seychas.

c=a+b
"""
from __future__ import annotations
import os, sys
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("diag_where", __name__)

@bp.get("/_where")
def where():
    app_mod = sys.modules.get("__main__")
    app_file = getattr(app_mod, "__file__", None)
    rules = sorted(r.rule for r in current_app.url_map.iter_rules())
    return jsonify(
        ok=True,
        cwd=os.getcwd(),
        app_file=app_file,
        app_root=current_app.root_path,
        template_folder=current_app.template_folder,
        static_folder=current_app.static_folder,
        have_portal=("/portal" in rules or "/portal/" in rules),
        routes=rules,
    )

def register(app):
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return True