# -*- coding: utf-8 -*-
"""routes/ester_memory_status_routes_alias.py

GET /ester/memory/status

Svodka po sostoyaniyu pamyati:
- store / backups, if available.
- Nalichie priority-helper.

Invariance:
- Just read.
- Pri otsutstvii modulary vozvraschaem warnings.

Mosty:
- Yavnyy: Memory ↔ operator/Ester.
- Skrytyy #1: Memory ↔ GC.
- Skrytyy #2: Memory ↔ self-evo."""

from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, jsonify  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import store as _store  # type: ignore
except Exception:  # pragma: no cover
    _store = None  # type: ignore

try:
    from modules.memory import backups as _backups  # type: ignore
except Exception:  # pragma: no cover
    _backups = None  # type: ignore

try:
    from modules.memory import memory_priority_profile_adapter as _prio  # type: ignore
except Exception:  # pragma: no cover
    _prio = None  # type: ignore

def _retention_telemetry() -> Dict[str, Any]:
    try:
        mem = list(getattr(_store, "_MEM", {}).values()) if _store is not None else []
    except Exception:
        mem = []
    pinned = 0
    decayed = 0
    by_type: Dict[str, int] = {}
    for r in mem:
        try:
            tp = (r.get("type") or r.get("kind") or "fact").lower()
            by_type[tp] = by_type.get(tp, 0) + 1
            meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
            if meta.get("pin"):
                pinned += 1
            if "decay_ts" in meta:
                decayed += 1
        except Exception:
            continue
    return {"pinned": pinned, "decayed": decayed, "by_type": by_type}


def create_blueprint() -> Blueprint:
    bp = Blueprint("ester_memory_status_routes", __name__, url_prefix="/ester/memory")

    @bp.get("/status")
    def memory_status() -> Any:
        out: Dict[str, Any] = {"ok": True, "warnings": []}

        if _store is not None and hasattr(_store, "get_stats"):
            try:
                out["store"] = _store.get_stats()  # type: ignore
            except Exception as e:
                out["warnings"].append(f"store_stats_error:{e!s}")
        elif _store is None:
            out["warnings"].append("store_missing")

        if _backups is not None and hasattr(_backups, "get_status"):
            try:
                out["backups"] = _backups.get_status()  # type: ignore
            except Exception as e:
                out["warnings"].append(f"backups_status_error:{e!s}")

        out["priority_helper"] = bool(_prio is not None)
        out["retention"] = _retention_telemetry()

        return jsonify(out)

    return bp


def register(app) -> None:  # pragma: no cover
    bp = create_blueprint()
    name = bp.name
    if getattr(app, "blueprints", None) and name in app.blueprints:
        return
    app.register_blueprint(bp)
    try:
        print("[ester-memory-status/routes] registered /ester/memory/status")
    except Exception:
        pass


def init_app(app) -> None:  # pragma: no cover
    register(app)


__all__ = ["create_blueprint", "register", "init_app"]
