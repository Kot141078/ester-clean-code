# -*- coding: utf-8 -*-
# routes/simple_login_routes.py
"""
routes/simple_login_routes.py — dev-only /auth/login (alternativa iz app._simple_auth).

Put:
  • POST /auth/login — JSON {user, role} v†' JWT (esli v okruzhenii vklyucheno ENABLE_SIMPLE_LOGIN=1)

Sovmestimost:
  • register_all.py podklyuchaet ETOT blyuprint tolko esli /auth/login esche ne suschestvuet.
  • Esli vklyuchen obrabotchik iz app.py, etot modul ne zaregistriruetsya (idempotentnost).

Zemnoy abzats (inzheneriya):
Zapasnoy «klyuch na gvozdike» dlya lokalnoy otladki. R' prode vyklyuchen flagom.

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): bystryy kanal vydachi tokena dlya testov.
- Skrytyy 1 (Infoteoriya v†" Interfeysy): minimalnyy JSON-kontrakt — prosche avtomatizirovat.
- Skrytyy 2 (Anatomiya v†" PO): kak «vremennaya shina» — udobno pri sborke, ubiraem pri zapuske.

# c=a+b
"""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import create_access_token  # type: ignore
except Exception:  # pragma: no cover
    create_access_token = None  # type: ignore

bp = Blueprint("simple_login_routes", __name__, url_prefix="/auth")

@bp.post("/login")
def login():
    if os.getenv("ENABLE_SIMPLE_LOGIN", "0") != "1":
        return jsonify({"ok": False, "error": "disabled"}), 403
    if not create_access_token:
        return jsonify({"ok": False, "error": "jwt_unavailable"}), 503
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    user = (data.get("user") or "user").strip()
    role = (data.get("role") or "user").strip()
    token = create_access_token(identity=user, additional_claims={"roles": [role], "user": user})
# return jsonify({"ok": True, "access_token": token, "user": user, "role": role})



def register(app):
    app.register_blueprint(bp)
    return app