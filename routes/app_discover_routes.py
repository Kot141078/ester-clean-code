
# -*- coding: utf-8 -*-
"""routes/app_discover_routes.py - discover/diagnostics endpoints (fixed).
Mosty: yavnyy (Veb↔Dvizhok deystviy), skrytye (Memory↔Inspektsiya; UI↔Diagnostika).
Zemnoy abzats: ruchki zdorovya/skanirovaniya marshrutov nuzhny dlya knopok “obnaruzhit/perezagruzit”.
Ranee padalo iz‑za opechatki jupytext(...) vmesto jsonify(...). Now everything is safe.
c=a+b"""
from __future__ import annotations
import importlib, os
from typing import Any, Dict, List, Tuple
from flask import Blueprint, jsonify, request, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("app_discover_routes", __name__, url_prefix="")

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

@bp.route("/app/discover/scan", methods=["GET"])
def api_scan():
    try:
        r = _collect_routes(current_app)
        return jsonify({"ok": True, "routes": r})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

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

@bp.route("/debug/actions/reload", methods=["POST"])
def debug_actions_reload():
    try:
        from modules.thinking.actions_discovery import discover_actions  # type: ignore
    except Exception:
        try:
            from actions_discovery import discover_actions  # type: ignore
        except Exception:
            discover_actions = None  # type: ignore
    try:
        if discover_actions is not None:
            try:
                reg = discover_actions(current_app, bootstrap=False)  # type: ignore
            except TypeError:
                reg = discover_actions(current_app)  # type: ignore
            count = len(reg) if reg is not None else 0
        else:
            try:
                from modules.thinking.action_registry import list_registered as _alist  # type: ignore
                count = len(_alist())
            except Exception:
                count = 0
        return jsonify({"ok": True, "registered": int(count)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.route("/debug/doctor", methods=["GET"])
def debug_doctor():
    try:
        try:
            from modules.health_check import HealthCheck  # type: ignore
            hc = HealthCheck()  # type: ignore
            checks = hc.run_all_checks()
            ok = True
            if isinstance(checks, dict):
                for v in checks.values():
                    if v is True:
                        continue
                    if isinstance(v, str) and "OK" in v:
                        continue
                    ok = False
                    break
            return jsonify({"ok": bool(ok), "system_health": checks}), 200
        except Exception as he:
            return jsonify({"ok": False, "error": f"health_check_unavailable:{he}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def register(app):
    app.register_blueprint(bp)
