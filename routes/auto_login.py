# -*- coding: utf-8 -*-
"""
routes/auto_login.py - servisnye ruchki dlya Papa (avto-JWT).

MOSTY:
- (Yavnyy) GET /auth/papa/token, POST /auth/papa/login - vydaet/ustanavlivaet JWT.
- (Skrytyy #1) /auth/me - bystro posmotret, kto v kuke (verify_jwt).
- (Skrytyy #2) Ne lomaet storonnie JWT-initsializatsii: eto parallelnyy put.

ZEMNOY ABZATs:
Knopka «voyti kak vladelets»: odin klik - i portal uzhe avtorizovan bez tantsev.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, make_response, request
from modules.auth.auto_jwt import mint_jwt, verify_jwt, ensure_papa_cookie
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("auto_login", __name__, url_prefix="/auth")

def register(app):
    app.register_blueprint(bp)

@bp.get("/papa/token")
def papa_token():
    user = os.getenv("ESTER_DEFAULT_USER", "Owner")
    tok = mint_jwt(user, roles=["admin","owner"])
    return jsonify({"ok": True, "user": user, "token": tok})

@bp.post("/papa/login")
def papa_login():
    user = (request.json or {}).get("user") or os.getenv("ESTER_DEFAULT_USER", "Owner")
    tok = mint_jwt(user, roles=["admin","owner"])
    resp = make_response(jsonify({"ok": True, "user": user}))
    try:
        resp.set_cookie("jwt", tok, httponly=True, samesite="Lax", max_age=30*86400, path="/")
        resp.set_cookie("Authorization", f"Bearer {tok}", httponly=False, samesite="Lax", max_age=30*86400, path="/")
    except Exception:
        pass
    return resp

@bp.get("/me")
def whoami():
    tok = request.cookies.get("jwt") or (request.headers.get("Authorization","").split("Bearer ") + [""])[-1]
    ok, payload = verify_jwt(tok) if tok else (False, None)
    return jsonify({"ok": ok, "payload": payload})
# c=a+b