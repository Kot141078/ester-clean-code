# -*- coding: utf-8 -*-
"""
routes/ester_will_plan_routes_alias.py

GET /ester/will/plan

Naznachenie:
- Dat cheloveku i samoy Ester strukturirovannyy plan zadach ot modulya voli.
- Plan stroitsya na osnove vnutrennikh endpointov:
  /ester/selfcheck, /ester/memory/status, /ester/will/status

Invarianty:
- Tolko chtenie, bez zapuska fonovykh deystviy.
- Ispolzuet app.test_client(), bez vneshnego HTTP.

Mosty:
- Yavnyy: Volya-planirovschik ↔ selfcheck/memory/will.
- Skrytyy #1: Plan ↔ chelovek-operator (Owner) dlya soglasovaniya.
- Skrytyy #2: Plan ↔ vozmozhnyy cron/async_jobs.

Zemnoy abzats:
Eto kak pechatnyy naryad-dopusk: spisok rabot po reglamentu,
no ispolnenie ostaetsya pod kontrolem.
"""

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.will import will_planner_adapter as _planner  # type: ignore
except Exception:  # pragma: no cover
    _planner = None  # type: ignore


def _probe(client, path: str, method: str = "GET") -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": False, "code": None, "data": None}
    try:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={"prompt": "will-plan-probe"})
        out["code"] = r.status_code
        if 200 <= r.status_code < 300:
            out["data"] = r.get_json(silent=True)
            out["ok"] = True
    except Exception as e:  # pragma: no cover
        out["data"] = {"error": str(e)}
    return out


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_will_plan_routes", __name__, url_prefix="/ester/will")

    @bp.get("/plan")
    def will_plan() -> Any:
        if _planner is None:
            return jsonify(
                {
                    "ok": False,
                    "reason": "will_planner_adapter_missing",
                    "tasks": [],
                }
            )

        app = current_app._get_current_object()
        client = app.test_client()

        snapshot: Dict[str, Any] = {}

        sc = _probe(client, "/ester/selfcheck")
        if sc["ok"]:
            snapshot["selfcheck"] = sc["data"] or {}

        ms = _probe(client, "/ester/memory/status")
        if ms["ok"]:
            snapshot["memory_status"] = ms["data"] or {}

        ws = _probe(client, "/ester/will/status")
        if ws["ok"]:
            snapshot["will_status"] = ws["data"] or {}

        plan = _planner.build_plan(snapshot)

        return jsonify(plan)

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-will-plan/routes] registered /ester/will/plan")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]