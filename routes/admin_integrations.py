# -*- coding: utf-8 -*-
"""
routes/admin_integrations.py - admin-ruchki dlya self-check integratsiy.

MOSTY:
- (Yavnyy) GET /admin/integrations/check - vozvraschaet otchet quick_check().
- (Skrytyy #1) Ne trebuet vneshnego interneta; offlayn validator ENV i faylov.
- (Skrytyy #2) Prednaznachen dlya portala/nablyudaemosti, ne lomaet RBAC/JWT politiku.

ZEMNOY ABZATs:
Kak indikator pitaniya: srazu vidno, podklyucheny li «provoda» k Telegram/WhatsApp i t.d.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_integrations", __name__, url_prefix="/admin/integrations")

def register(app):
    app.register_blueprint(bp)

@bp.get("/check")
def check():
    try:
        from modules.integrations.checks import quick_check  # type: ignore
        return jsonify(quick_check())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
# c=a+b