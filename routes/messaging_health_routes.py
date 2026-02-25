# -*- coding: utf-8 -*-
"""routes/messaging_health_routes.py - health/readiness/liveness dlya messaging-steka.

MOSTY:
- (Yavnyy) Signaly dlya orkestratora i cheloveka: what skonfigurirovano, what zagruzheno, what sukho (dry).
- (Skrytyy #1) Test zagruzki pravil PROACTIVE_RULES_PATH i WILL_MAP_PATH bez pobochnykh effektov.
- (Skrytyy #2) Diagnostika okruzheniya: tokeny/ID prisutstvuyut, no v otvete ne utekut (boolean only).

ZEMNOY ABZATs:
Daet bystryy “svetofor” - mozhno li bezopasno vklyuchat Ester-messendzhery v prod i zhdat soobscheniy.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml
except Exception:
    yaml = None

bp = Blueprint("messaging_health_routes", __name__)

def _exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except Exception:
        return False

def _yaml_ok(path: str) -> bool:
    if not yaml or not _exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            _ = yaml.safe_load(f)
        return True
    except Exception:
        return False

@bp.route("/messaging/liveness", methods=["GET"])
def liveness():
    return jsonify({"ok": True})

@bp.route("/messaging/readiness", methods=["GET"])
def readiness():
    rules = os.environ.get("PROACTIVE_RULES_PATH", "config/messaging_rules.yaml")
    will = os.environ.get("WILL_MAP_PATH", "config/will_messaging_map.yaml")
    return jsonify({
        "ok": True,
        "rules_loaded": _yaml_ok(rules),
        "will_map_loaded": _yaml_ok(will),
    })

@bp.route("/messaging/health", methods=["GET"])
def health():
    tg = bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip())
    wa_token = bool(os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip())
    wa_id = bool(os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip())
    return jsonify({
        "ok": True,
        "telegram": {"configured": tg, "mode": "real" if tg else "dry"},
        "whatsapp": {"configured": wa_token and wa_id, "mode": "real" if (wa_token and wa_id) else "dry"},
    })

def register(app):
    app.register_blueprint(bp)
    return bp