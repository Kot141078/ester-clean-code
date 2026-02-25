# -*- coding: utf-8 -*-
"""routes/ester_selfmod_routes_alias.py

Marshruty upravleniya bezopasnym samoizmeneniem Ester.

POST /ester/selfmod/propose
- Accept predlozhenie izmeneniy (JSON).
- Delegiruet v modules.ester.self_mod_executor.apply(...).
- Ne trebuet vneshnikh klyuchey, rabotaet lokalno.

GET /ester/selfmod/status
- Pokazyvaet tekuschiy rezhim A/B i politiku soglasiya.

Invariance:
- Ne zapuskaet izmeneniya bez ESTER_SELF_MOD_AB=B i soglasiya.
- Ne menyaet suschestvuyuschie kriticheskie fayly.
- Net fonovykh demonov.

Mosty:
- Yavnyy: HTTP ↔ self_mod_executor (chetkaya tochka vkhoda).
- Skrytyy #1: selfmod ↔ volya (cherez pole source i ENV).
- Skrytyy #2: selfmod ↔ operator (Owner) — prozrachnyy otchet.

Zemnoy abzats:
Kak pult “Razreshit avtoobnovlenie chertezhey”: poka flazhok ne v B,
nichego ne perepishetsya bez tvoego i ee pryamogo soglasiya."""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester import self_mod_executor  # type: ignore
except Exception:  # pragma: no cover
    self_mod_executor = None  # type: ignore


def _mode() -> str:
    return (os.getenv("ESTER_SELF_MOD_AB") or "A").strip().upper() or "A"


def _allow_ester() -> bool:
    v = (os.getenv("ESTER_SELF_MOD_ALLOW_ESTER") or "0").strip()
    return v in ("1", "true", "True")


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_selfmod_routes", __name__, url_prefix="/ester/selfmod")

    @bp.get("/status")
    def status() -> Any:
        return jsonify(
            {
                "ok": True,
                "mode": _mode(),
                "allow_ester": _allow_ester(),
            }
        )

    @bp.post("/propose")
    def propose() -> Any:
        if self_mod_executor is None:
            return jsonify(
                {
                    "ok": False,
                    "reason": "self_mod_executor_missing",
                }
            ), 500

        app = current_app._get_current_object()
        root_dir = app.root_path  # koren proekta

        try:
            data: Dict[str, Any] = request.get_json(force=True, silent=False)  # type: ignore
        except Exception as e:  # pragma: no cover
            return jsonify({"ok": False, "error": f"invalid_json:{e}"}), 400

        report = self_mod_executor.apply(root_dir, data)
        code = 200 if report.get("ok") else 400
        return jsonify(report), code

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-selfmod/routes] registered /ester/selfmod/status,/ester/selfmod/propose")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]