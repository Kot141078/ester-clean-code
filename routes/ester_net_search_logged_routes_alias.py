# -*- coding: utf-8 -*-
# routes/ester_net_search_logged_routes_alias.py
#
# POST /ester/net/search_logged
#
# Naznachenie:
# - Use a network bridge so that each request:
#   * went through the politics of will and autonomy,
#   * if successful, it was recorded in memory as a conscious action.
#
# Request contract:
# {
#   "to": "query string",
#   "limit": 5,
#   "source": "operator" | "ester"
# }
#
# Invarianty:
# - Does not create background tasks.
# - Does not change memory directly, only through events_unified_adapter (if available).
# - Respects the same rules as /ester/no/search.

from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request, current_app  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester import net_will_adapter  # type: ignore
except Exception:  # pragma: no cover
    net_will_adapter = None  # type: ignore


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_net_search_logged_routes", __name__, url_prefix="/ester/net")

    @bp.post("/search_logged")
    def search_logged() -> Any:
        if net_will_adapter is None:
            return jsonify(
                {
                    "ok": False,
                    "reason": "net_will_adapter_missing",
                }
            ), 500

        try:
            payload: Dict[str, Any] = request.get_json(force=True, silent=False)  # type: ignore
        except Exception as e:  # pragma: no cover
            return jsonify({"ok": False, "reason": f"invalid_json:{e}"}), 400

        q = str(payload.get("q") or payload.get("query") or "").strip()
        limit = payload.get("limit", 5)
        source = (payload.get("source") or "operator").strip().lower()

        try:
            limit_int = int(limit)
        except Exception:
            limit_int = 5

        app = current_app._get_current_object()
        result = net_will_adapter.search_and_log(
            app=app,
            query=q,
            limit=limit_int,
            source=source,
        )

        code = 200 if result.get("ok") else 400
        return jsonify(result), code

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-net-search-logged/routes] registered /ester/net/search_logged")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]