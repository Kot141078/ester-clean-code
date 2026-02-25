# -*- coding: utf-8 -*-
"""/portal: sovmestimyy legacy-entry.

Kanonicheskiy vkhod teper /admin/portal, zdes ostavlyaem tolko 302-redirekt.

Mosty:
- Yavnyy: HTTP ↔ fayl shablona.
- Skrytye: ENV↔FS (ESTER_PROJECT_ROOT), Jinja↔Fallback.

Zemnoy abzats:
Staryy vyklyuchatel ostavlen, no wire pereveden na novuyu klemmu.

c=a+b"""
from __future__ import annotations
from flask import Blueprint, redirect
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portal_fallback_force", __name__)

@bp.get("/portal")
@bp.get("/portal/")
def portal():
    return redirect("/admin/portal", code=302)

def register(app):
    if bp.name not in app.blueprints:
        app.register_blueprint(bp)
    return True
