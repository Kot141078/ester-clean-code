# -*- coding: utf-8 -*-
"""Marshruty statusa myshleniya Ester.

GET /ester/thinking/status
- otdaet svodnye stats ot thinking_trace_adapter (esli on est),
  ne vmeshivayas v osnovnoy manifest/quality."""
from __future__ import annotations

from typing import Any
from flask import Blueprint, jsonify  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.ester import thinking_trace_adapter as _trace  # type: ignore
except Exception:  # pragma: no cover
    _trace = None  # type: ignore


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_thinking_status_routes", __name__, url_prefix="/ester/thinking")

    @bp.get("/status")
    def thinking_status() -> Any:
        out = {"ok": True}
        if _trace is not None and hasattr(_trace, "get_stats"):
            try:
                out["trace"] = _trace.get_stats()
            except Exception as e:
                out.setdefault("warnings", []).append(f"trace_error:{e!s}")
        else:
            out.setdefault("warnings", []).append("thinking_trace_adapter_missing")
        return jsonify(out)

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-thinking-status/routes] registered /ester/thinking/status")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]