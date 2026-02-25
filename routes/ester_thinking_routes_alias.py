# -*- coding: utf-8 -*-
"""routes/ester_thinking_routes_alias.py

HTTP-vkhod dlya kaskadnogo myshleniya Ester.

Mosty:
- Yavnyy: (HTTP ↔ always_thinker / kaskad) - odin endpoint dlya zapuska osmyslennogo kaskada.
- Skrytyy #1: (Volya/prioritety ↔ tsel) — umeet prokinut goal cherez ochered prioritetov.
- Skrytyy #2: (Treys ↔ chelovek) — po flagu vozvraschaet tekstovoe obyasnenie khoda mysley.

Zemnoy abzats:
Inzhener shlet POST /ester/thinking/once s goal – Ester zapuskaet kaskad,
ispolzuya tekuschie rezhimy (volya, mnogokontekst, guard) i vozvraschaet summary + (opts.) treys.
Tak proveryaetsya, chto ona dumaet kak chelovek, no ustoychivee, chem biologiya.
# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask import Blueprint, jsonify, request
except Exception:  # pragma: no cover
    Blueprint = None  # type: ignore
    jsonify = None    # type: ignore
    request = None    # type: ignore


def _safe_import(modname: str, attr: str = None):
    """Best - Efficient import without crashing the application."""
    try:
        module = __import__(modname, fromlist=[attr] if attr else [])
    except Exception:
        return None
    if attr:
        return getattr(module, attr, None)
    return module


def _extract_summary(res: Any) -> str:
    if isinstance(res, dict):
        if "summary" in res and isinstance(res["summary"], str):
            return res["summary"]
        inner = res.get("result")
        if isinstance(inner, dict) and isinstance(inner.get("summary"), str):
            return inner["summary"]
    return ""


def _with_trace(base_res: Any) -> Dict[str, Any]:
    """Return a human-readable trace if thught_trace_adapter is available."""
    tta = _safe_import("modules.thinking.thought_trace_adapter")
    if tta is None:
        return {}
    try:
        data = base_res
        if isinstance(base_res, dict) and "result" in base_res:
            data = base_res["result"]
        info = tta.from_cascade_result(data)  # type: ignore[attr-defined]
        if isinstance(info, dict) and info.get("text"):
            return {"trace": info.get("text"), "trace_meta": info.get("info")}
    except Exception:
        return {}
    return {}


def create_blueprint():
    if Blueprint is None or jsonify is None or request is None:
        return None

    bp = Blueprint("ester_thinking_bp", __name__, url_prefix="/ester/thinking")

    @bp.route("/ping", methods=["GET"])
    def ping() -> Any:  # pragma: no cover
        return jsonify({"ok": True, "msg": "Ester thinking entry is alive"})

    @bp.route("/once", methods=["POST"])
    def once() -> Any:  # pragma: no cover
        data = request.get_json(silent=True) or {}
        goal = (data.get("goal") or "diagnostic cascade ping").strip()
        priority = str(data.get("priority") or "normal").lower()
        want_trace = bool(data.get("trace") or False)

        used: List[str] = []
        res: Any = None

        # 1) Pytaemsya ispolzovat polnyy stek always_thinker + prioritety.
        at = _safe_import("modules", "always_thinker")
        vpa = _safe_import("modules.thinking.volition_priority_adapter", "enqueue")
        if at is not None and hasattr(at, "consume_once") and callable(getattr(at, "consume_once")):
            try:
                meta: Dict[str, Any] = {}
                if priority in ("high", "low"):
                    meta["priority"] = priority
                if callable(vpa):
                    vpa(goal, meta)  # type: ignore[misc]
                    used.append("volition_priority_adapter.enqueue")
                r = at.consume_once()  # type: ignore[attr-defined]
                if r:
                    res = r
                    used.append("always_thinker.consume_once")
            except Exception:
                res = None

        # 2) Fallback: mnogokontekstnyy kaskad.
        if res is None:
            cmc = _safe_import("modules.thinking.cascade_multi_context_adapter")
            if cmc is not None and hasattr(cmc, "run") and callable(getattr(cmc, "run")):
                try:
                    res = cmc.run(goal)  # type: ignore[attr-defined]
                    used.append("cascade_multi_context_adapter.run")
                except Exception:
                    res = None

        # 3) Fallback: bazovyy zakrytyy kaskad.
        if res is None:
            cc = _safe_import("modules.thinking.cascade_closed")
            if cc is not None and hasattr(cc, "run_cascade") and callable(getattr(cc, "run_cascade")):
                try:
                    res = cc.run_cascade(goal)  # type: ignore[attr-defined]
                    used.append("cascade_closed.run_cascade")
                except Exception:
                    res = None

        if res is None:
            return jsonify({"ok": False, "error": "no thinking backend available", "used": used}), 500

        payload: Dict[str, Any] = {
            "ok": True,
            "goal": goal,
            "used": used,
            "summary": _extract_summary(res),
            "raw": res,
        }

        if want_trace:
            payload.update(_with_trace(res))

        return jsonify(payload)

    return bp


def register(app) -> None:
    """Autoload_rutes_fs() is called from the application (AUTO-REG via FSS)."""
    bp = create_blueprint()
    if not bp:
        return
    name = getattr(bp, "name", "ester_thinking_bp")
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)