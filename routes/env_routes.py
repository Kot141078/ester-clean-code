# -*- coding: utf-8 -*-
"""
routes/env_routes.py - status i peresborka .env.

MOSTY:
- (Yavnyy) GET /env/status - svodka po klyucham; POST /env/rebuild {public_only}
- (Skrytyy #1) Delegiruet rebuild v tools/env/rebuild_env.py.
- (Skrytyy #2) Umeet vypuskat .env.public (dlya publichnogo eksporta) bez izmeneniya lokalnogo .env.

ZEMNOY ABZATs:
Pult «pitanie/kabeli»: bystro vidno, chto podklyucheno, i srazu mozhno sobrat publichnyy .env.

# c=a+b
"""
from __future__ import annotations
import os, json
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("env_routes", __name__, url_prefix="/env")

def register(app):
    app.register_blueprint(bp)

@bp.get("/status")
def status():
    keys = [
        "OPENAI_API_KEY","GEMINI_API_KEY","XAI_API_KEY",
        "TELEGRAM_BOT_TOKEN","TELEGRAM_WEBHOOK_SECRET",
        "WHATSAPP_ACCESS_TOKEN","WHATSAPP_PHONE_NUMBER_ID","WHATSAPP_VERIFY_TOKEN",
        "JWT_SECRET","JWT_SECRET_KEY","P2P_HMAC_KEY"
    ]
    env = {k: bool(os.getenv(k,"").strip()) for k in keys}
    return jsonify({"ok": True, "env": env})

@bp.post("/rebuild")
def rebuild():
    body = request.get_json(silent=True) or {}
    public_only = bool(body.get("public_only", False))
    try:
        from tools.env.rebuild_env import rebuild_env  # type: ignore
        res = rebuild_env(public_only=public_only)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
# c=a+b