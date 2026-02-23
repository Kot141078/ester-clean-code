# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from flask import Blueprint, request, jsonify, abort
from modules.security.jwt_owner import generate_owner_jwt
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("jwt_owner_routes", __name__)
_AB = os.getenv("ESTER_JWT_OWNER_AB", "A").upper()

@_bp.get("/_auth/owner/jwt")
def _owner_jwt():
    if _AB != "B":
        abort(404)
    pin = request.args.get("pin", "")
    expected = os.getenv("ESTER_OWNER_PIN", "")
    if not expected or pin != expected:
        return jsonify({"ok": False, "error": "invalid_pin"}), 403
    info = generate_owner_jwt(save_to=os.path.join("data", "owner_jwt.token"))
    return jsonify({"ok": True, "token": info["token"], "roles": info["payload"]["roles"], "exp": info["payload"]["exp"]})

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
# c=a+b