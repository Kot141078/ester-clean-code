# -*- coding: utf-8 -*-
# routes/ester_will_plan_ext_routes_alias.py
#
# GET /ester/will/plan_ext
#
# Rasshirennaya versiya plana voli.
# Delaet GET /ester/will/plan, zatem cherez net_will_adapter dobavlyaet setevye zadachi.
# Bazovyy kontrakt /ester/will/plan ne menyaetsya.

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester import net_will_adapter  # type: ignore
except Exception:  # pragma: no cover
    net_will_adapter = None  # type: ignore


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_will_plan_ext_routes", __name__, url_prefix="/ester/will")

    @bp.get("/plan_ext")
    def plan_ext() -> Any:
        app = current_app._get_current_object()
        client = app.test_client()

        r = client.get("/ester/will/plan")
        if r.status_code != 200:
            return jsonify(
                {
                    "ok": False,
                    "reason": "will_plan_unavailable",
                    "code": r.status_code,
                }
            ), 500

        base_plan: Dict[str, Any] = r.get_json(silent=True) or {}

        if net_will_adapter is None:
            return jsonify(base_plan)

        autonomy = net_will_adapter.get_autonomy(app)
        extended = net_will_adapter.extend_plan_with_net(base_plan, autonomy)
        return jsonify(extended)

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-will-plan-ext/routes] registered /ester/will/plan_ext")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]