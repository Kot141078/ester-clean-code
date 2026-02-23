# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.autonomy import state as autonomy_state  # type: ignore
except Exception:  # pragma: no cover
    autonomy_state = None  # type: ignore

try:
    from modules.will import consent_gate as will_consent  # type: ignore
except Exception:  # pragma: no cover
    will_consent = None  # type: ignore

try:
    from modules.will import unified_guard_adapter as will_guard  # type: ignore
except Exception:  # pragma: no cover
    will_guard = None  # type: ignore

def create_blueprint() -> Blueprint | None:
    bp = Blueprint("ester_will_status_routes", __name__, url_prefix="/ester/will")

    @bp.get("/status")
    def will_status() -> Any:
        out: Dict[str, Any] = {"ok": True}
        if autonomy_state is not None:
            try:
                out["autonomy"] = autonomy_state.get()
            except Exception as e:
                out.setdefault("warnings", []).append(f"autonomy_state_error:{e!s}")
        else:
            out.setdefault("warnings", []).append("autonomy_state_missing")

        if will_consent is not None:
            try:
                base = will_consent.check(need=None, min_level=0)  # type: ignore[arg-type]
                out["will_probe"] = {k: v for k, v in base.items() if k != "snapshot"}
            except Exception as e:
                out.setdefault("warnings", []).append(f"will_probe_error:{e!s}")
        else:
            out.setdefault("warnings", []).append("will_consent_missing")

        if will_guard is not None:
            try:
                mode = will_guard._ab_mode() if hasattr(will_guard, "_ab_mode") else None  # type: ignore[attr-defined]
            except Exception:
                mode = None
            if mode:
                out["unified_guard"] = {"mode": mode}
            else:
                out.setdefault("warnings", []).append("unified_guard_mode_unknown")
        else:
            out.setdefault("warnings", []).append("unified_guard_missing")

        return jsonify(out)

    return bp

def register(app):  # pragma: no cover
    bp = create_blueprint()
    if bp is None:
        return
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    print("[ester-will-status/routes] registered /ester/will/status")

def init_app(app):  # pragma: no cover
    register(app)

__all__ = ["create_blueprint", "register", "init_app"]