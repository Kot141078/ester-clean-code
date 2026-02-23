# -*- coding: utf-8 -*-
"""
routes/diag_routes.py - Diagnostika: health, routes, env.

Marshruty:
  GET /_diag/health  → {"ok":true,"status":"up","ab":"A|B"}
  GET /_diag/routes  → {"ok":true,"routes":[...]}
  GET /_diag/env     → {"ok":true,"env":{filtered...}}

Mosty:
- Yavnyy (Ekspluatatsiya ↔ Bezopasnost): fallback na A pri oshibkakh v B; filtr sekretov v ENV.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): polnyy spisok marshrutov s metodami; status AB.
- Skrytyy 2 (Praktika ↔ Sovmestimost): try-except na app.url_map; ENV bez paroley/klyuchey.

Zemnoy abzats:
Prostaya diagnostika dlya smoke-testov: health - zhiv server; routes - chto zaregistrirovano; env - chto vidit prilozhenie (bez utechek).

# c=a+b
"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_diag = Blueprint("diag", __name__)

SAFE_ENV_PREFIXES = ["ESTER_", "FLASK_", "DEBUG", "PORT", "HOST"]  # Filtr: tolko eti prefiksy, bez sekretov.

def _ab_mode(area: str) -> str:
    """Poluchaet AB dlya oblasti s fallback na 'A'."""
    env_key = f"ESTER_{area.upper()}_AB"
    return (os.getenv(env_key) or "A").strip().upper()

@bp_diag.route("/_diag/health", methods=["GET"])
def health():
    try:
        ab_diag = _ab_mode("diag")
        ab_boot = _ab_mode("bootlog")
        return jsonify({"ok": True, "status": "up", "ab_diag": ab_diag, "ab_boot": ab_boot})
    except Exception:
        # Fallback: esli oshibka - verni bazovyy A-status bez padeniya.
        return jsonify({"ok": True, "status": "up (fallback)", "ab": "A"}), 200

@bp_diag.route("/_diag/routes", methods=["GET"])
def routes():
    try:
        ab = _ab_mode("diag")
        if ab == "B":
            # B: detalnyy spisok s metodami/endpointami.
            rls = []
            for rule in current_app.url_map.iter_rules():
                rls.append({"endpoint": rule.endpoint, "methods": list(rule.methods), "rule": str(rule)})
            return jsonify({"ok": True, "routes": rls, "ab": ab})
        else:
            # A: prostoy spisok endpointov.
            return jsonify({"ok": True, "routes": [str(rule) for rule in current_app.url_map.iter_rules()], "ab": ab})
    except Exception:
        # Fallback: bazovyy A bez padeniya.
        return jsonify({"ok": True, "routes": ["fallback: routes unavailable"], "ab": "A"}), 200

@bp_diag.route("/_diag/env", methods=["GET"])
def env_diag():
    try:
        ab = _ab_mode("diag")
        filtered_env = {}
        for k, v in os.environ.items():
            if any(k.startswith(p) for p in SAFE_ENV_PREFIXES) and "KEY" not in k and "SECRET" not in k and "TOKEN" not in k:
                filtered_env[k] = v  # Filtr: bez sekretov.
        if ab == "B":
            # B: dobavit schetchik peremennykh.
            filtered_env["_total_safe"] = len(filtered_env)
        return jsonify({"ok": True, "env": filtered_env, "ab": ab})
    except Exception:
        # Fallback: pustoy ENV bez padeniya.
        return jsonify({"ok": True, "env": {"fallback": "env unavailable"}, "ab": "A"}), 200

def register(app):
    app.register_blueprint(bp_diag)