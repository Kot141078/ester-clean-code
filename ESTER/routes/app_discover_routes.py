
# -*- coding: utf-8 -*-
"""
ester/routes/app_discover_routes.py — bezopasnaya versiya ruchek discover (namespace-put).
Stavit tu zhe semantiku, chto i routes/app_discover_routes.py, no ostaetsya sovmestimoy.
c=a+b
"""
from __future__ import annotations
import importlib
from typing import Any, Dict, List, Tuple
from flask import Blueprint, jsonify, request, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ester_app_discover_routes", __name__, url_prefix="")

def _collect_routes(app) -> Dict[str, Any]:
    out = []
    try:
        rules = list(app.url_map.iter_rules())
        for r in rules:
            methods = sorted(m for m in r.methods if m not in ("HEAD","OPTIONS"))
            out.append({"path": str(r.rule), "methods": methods, "endpoint": r.endpoint})
        out = sorted(out, key=lambda x: x["path"])
        return {"count": len(out), "items": out[:500]}
    except Exception as e:
        return {"error": str(e), "count": 0, "items": []}

def _safe_direct_register(app, dotted: str) -> Tuple[bool, str]:
    try:
        mod = importlib.import_module(dotted)
    except Exception as e:
        return False, f"import:{e}"
    try:
        if hasattr(mod, "register") and callable(getattr(mod, "register")):
            mod.register(app)
        elif hasattr(mod, "bp"):
            app.register_blueprint(getattr(mod, "bp"))
        return True, "ok"
    except Exception as e:
        return False, f"register:{e}"

@bp.route("/app/discover/status", methods=["GET"])
def api_status():
    try:
        try:
            from modules.thinking.action_registry import list_registered as _alist  # type: ignore
            ac = len(_alist())
        except Exception:
            ac = 0
        routes = _collect_routes(current_app)
        return jsonify({"ok": True, "routes": routes.get("count", 0), "actions": ac})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route("/app/discover/scan", methods=["GET"])
def api_scan():
    try:
        r = _collect_routes(current_app)
        return jsonify({"ok": True, "routes": r})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route("/app/discover/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True, silent=True) or {}
    mods = list(d.get("modules") or [])
    done: List[str] = []
    errs: Dict[str, str] = {}
    for m in mods:
        ok, note = _safe_direct_register(current_app, str(m))
        (done if ok else errs).__setitem__(m, note) if not ok else done.append(m)
    return jsonify({"ok": True, "registered": done, "errors": errs})

def register(app):
    app.register_blueprint(bp)