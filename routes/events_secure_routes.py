# -*- coding: utf-8 -*-
"""
routes/events_secure_routes.py - bezopasnaya publikatsiya sobytiy s verifikatsiey podpisi.

Podklyuchi v app.py:

    from routes.events_secure_routes import bp_events_secure, register, init_app
    app.register_blueprint(bp_events_secure)

Endpointy:
  POST /events.secure/publish   - prinimaet podpisannoe sobytie, validiruet, forvardit v obychnyy /events/publish
  GET  /events.secure/trust     - pokazat tekuschiy trust/caps (bez privatnykh klyuchey)
  POST /events.secure/register  - (optsionalno) zaregistrirovat novogo agenta (kid,pubkey,role)

# c=a+b
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict

from flask import Blueprint, jsonify, request

# Kontrakty moduley ne menyaem - myagkiy import
from modules.security.provenance import _load_registries, forward_to_bus, verify_event  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_events_secure = Blueprint("events_secure", __name__, url_prefix="/events.secure")
_write_lock = threading.Lock()

TRUST_PATH = Path("rules/trust_registry.yaml")


@bp_events_secure.post("/publish")
def publish_secure():
    """Prinyat podpisannoe sobytie, proverit podpis/rol i otpravit v obychnuyu shinu sobytiy."""
    try:
        ev: Dict[str, Any] = request.get_json(force=True, silent=False)  # ozhidaem JSON
    except Exception:
        return jsonify({"ok": False, "error": "bad_json"}), 400
    if not isinstance(ev, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    verdict = verify_event(ev)
    if not verdict or not verdict.get("ok"):
        return jsonify({"ok": False, "error": verdict or {"code": "verify_failed"}}), 403

    try:
        code = forward_to_bus(ev)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "status": code, "role": verdict.get("role")})


@bp_events_secure.get("/trust")
def get_trust_caps():
    """Otdat publichnye svedeniya iz reestrov doveriya (bez privatnykh klyuchey/sekretov)."""
    trust, caps = _load_registries()
    # Ne raskryvaem privatnye dannye; tolko bezopasnye polya
    return jsonify(
        {
            "ok": True,
            "trust": [
                {
                    "agent_id": a.get("agent_id"),
                    "kid": a.get("kid"),
                    "role": a.get("role"),
                    "status": a.get("status", "active"),
                }
                for a in trust.get("agents", [])
            ],
            "caps": caps.get("roles", {}),
        }
    )


@bp_events_secure.post("/register")
def register_agent():
    """
    Prostaya registratsiya agenta: {agent_id, kid, pubkey_base64, role}
    Dlya prodakshena dobav mTLS/admin-token - zdes demonstratsionnyy variant.
    """
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "bad_json"}), 400

    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    req = {k: data.get(k) for k in ("agent_id", "kid", "pubkey_base64", "role")}
    if not all(req.values()):
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    trust, _caps = _load_registries()
    with _write_lock:
        agents = list(trust.get("agents", []))
        # Zamenim/dobavim zapis po kid
        agents = [a for a in agents if a.get("kid") != req["kid"]]
        agents.append(
            {
                "agent_id": req["agent_id"],
                "kid": req["kid"],
                "pubkey_base64": req["pubkey_base64"],
                "role": req["role"],
                "status": "active",
            }
        )
        trust["agents"] = agents
        TRUST_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRUST_PATH.write_text(json.dumps(trust, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify(
        {
            "ok": True,
            "registered": {
                "agent_id": req["agent_id"],
                "kid": req["kid"],
                "role": req["role"],
            },
        }
    )


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp_events_secure)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp_events_secure", "register", "init_app"]