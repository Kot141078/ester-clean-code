# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Any, Dict, List

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _init_trace(app):
    if not hasattr(app, "trace_events"):
        app.trace_events = []  # type: ignore[attr-defined]


def _push(app, evt: str):
    _init_trace(app)
    app.trace_events.append(f"{time.strftime('%H:%M:%S')} {evt}")  # type: ignore[attr-defined]
    app.trace_events = app.trace_events[-200:]  # type: ignore[attr-defined]


def register_trace_routes(app, url_prefix: str = "/trace"):
    bp = Blueprint("trace", __name__)
    _init_trace(app)

    @bp.get(url_prefix + "/status")
    def trace_status():
        _push(app, "trace_status")
        return jsonify({"ok": True, "events": len(app.trace_events)})  # type: ignore[attr-defined]

    @bp.get(url_prefix + "/events")
    def trace_events():
        return jsonify({"events": list(getattr(app, "trace_events", []))})

# app.register_blueprint(bp)