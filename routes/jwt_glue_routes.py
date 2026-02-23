# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import (
    jwt_required,
    get_jwt,
    create_access_token,
)

# 1) Gotovyy Blueprint — bolshinstvo loaderov umeyut registrirovat ego sami
bp = Blueprint("jwt_glue", __name__)

@bp.get("/auth/glue/status")
def glue_status():
    cfg = current_app.config
    return jsonify({
        "ok": True,
        "ab": os.getenv("ESTER_JWT_BOOTSTRAP_AB", "A"),
        "alg": cfg.get("JWT_ALGORITHM"),
        "locations": cfg.get("JWT_TOKEN_LOCATION"),
        "header_name": cfg.get("JWT_HEADER_NAME"),
        "header_type": cfg.get("JWT_HEADER_TYPE"),
        "query_name": cfg.get("JWT_QUERY_STRING_NAME", "jwt"),
        "has_secret": bool(cfg.get("JWT_SECRET_KEY")),
    })

@bp.post("/auth/glue/mint")
def glue_mint():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    sub = data.get("sub") or data.get("subject") or "user"
    roles_val = data.get("roles") or data.get("role") or ["USER"]
    roles: List[str] = [roles_val] if isinstance(roles_val, str) else list(roles_val)
    token = create_access_token(identity=sub, additional_claims={"roles": roles})
    return jsonify(ok=True, token=token)

@bp.post("/auth/glue/verify")
@jwt_required()
def glue_verify():
    return jsonify(ok=True, claims=get_jwt())

# 2) Universalnye «kryuchki» — na sluchay, esli loader zhdet fabriku
def init_app(app):  # pragma: no cover
    try:
        if "jwt_glue" not in getattr(app, "blueprints", {}):
            app.register_blueprint(bp)
    except Exception:
        # esli uzhe zaregistrirovan — molchim
        pass

def register(app):  # pragma: no cover
    return init_app(app)
