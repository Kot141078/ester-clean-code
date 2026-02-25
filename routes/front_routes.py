# -*- coding: utf-8 -*-
"""routes/front_routes.py - vspomogatelnyy alias-redirekt bez zakhvata kornya.

Idea: koren (/) dolzhen ostavatsya kanonicheskim v root_routes.py.
Zdes ostavlyaem tolko vspomogatelnyy route /_alias/root_redirect.

Mosty:
  • Yavnyy: (Arkhitektura PO ↔ UX) - korotkiy put do paneli.
  • Skrytye: (Infoteoriya ↔ Nablyudaemost), (Anatomiya ↔ Navigatsiya).

Zemnoy abzats:
  Kak tablichka “Resepshn → napravo” u vkhoda - chtoby ne bluzhdat po pustomu khollu.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, current_app, redirect, url_for
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

front_bp = Blueprint("front", __name__)
bp = front_bp

@front_bp.route("/_alias/root_redirect", methods=["GET"])
def _root_redirect():
    return redirect("/admin/portal", code=302)

def register(app):
    app.register_blueprint(bp)
# c=a+b
