# -*- coding: utf-8 -*-
from __future__ import annotations

"""routes_memory.py - REST API dlya pamyati (v9).

Endpoint:
- GET /memory/flashback?user=&q=&k=
- GET /memory/stats
- POST /memory/alias {"old_doc_id": "...", "new_doc_id": "..."}
  (takzhe prinimayutsya klyuchi old_id/new_id)
- POST /memory/compact {"dry_run": true}

Dizayn-printsipy:
- ne padat iz-za nesovpadeniya API u memory_manager (sovmestimost s raznymi versiyami);
- predskazuemye kody oshibok: 400 (vvod), 503 (net memory_manager), 500 (oshibka vypolneniya);
- maximum poleznoy diagnostiki v logakh, minimum utechek steka v otvet polzovatelyu."""

import inspect
import logging
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, current_app, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

memory_bp = Blueprint("memory", __name__)


# --------- helpers ---------
def _get_mm() -> Any:
    """
    Poluchit memory_manager.
    Podderzhivaem dve modeli:
    - app.memory_manager (atribut)
    - app.extensions['memory_manager']
    """
    mm = getattr(current_app, "memory_manager", None)
    if mm is not None:
        return mm
    try:
        ext = getattr(current_app, "extensions", {}) or {}
        return ext.get("memory_manager")
    except Exception:
        return None


def _parse_k(raw: Any, default: int = 8, min_k: int = 1, max_k: int = 50) -> int:
    try:
        k = int(raw)
    except Exception:
        k = int(default)
    if k < min_k:
        k = min_k
    if k > max_k:
        k = max_k
    return k


def _call_flashback(mm: Any, user: str, query: str, k: int):
    """Compatibility:
    - new version: mm.flashtank(cuers, k)
    - old version: mm.flashtank(user=user, kuery=kuery, k=k) or mm.flashtank(user, kuery, k)"""
    fn = getattr(mm, "flashback", None)
    if not callable(fn):
        raise AttributeError("memory_manager.flashback not callable")

    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        # methods: the first parameter self is already “bound”, signature() sees the real signature as declared
        names = [p.name for p in params]
        # 1) po imenam
        if "user" in names and ("query" in names or "q" in names):
            # podderzhim query/q
            if "query" in names:
                return fn(user=user, query=query, k=k)
            return fn(user=user, q=query, k=k)
        # 2) bez user
        if "query" in names:
            return fn(query, k=k)  # pozitsionno query
        if "q" in names:
            return fn(q=query, k=k)
    except Exception:
        # if something went wrong with the introspect - falsify below
        pass

    # Fallback: poprobuem rasprostranennye varianty vyzova
    try:
        return fn(query, k=k)
    except TypeError:
        return fn(user, query, k)


def _call_alias(mm: Any, old_id: str, new_id: str) -> Dict[str, Any]:
    """Compatibility:
    - new version: mm.alias(old_id, new_id)
    - old version: mm.alias_daughter_id(old_id, new_id)"""
    if hasattr(mm, "alias") and callable(getattr(mm, "alias")):
        res = mm.alias(old_id, new_id)
        return res if isinstance(res, dict) else {"ok": True, "result": res}

    if hasattr(mm, "alias_doc_id") and callable(getattr(mm, "alias_doc_id")):
        res = mm.alias_doc_id(old_id, new_id)
        return res if isinstance(res, dict) else {"ok": True, "result": res}

    raise AttributeError("memory_manager alias method not found")


# --------- routes ---------
@memory_bp.get("/flashback")
def memory_flashback():
    try:
        user = str(request.args.get("user", "*") or "*")
        q = (request.args.get("q", "") or request.args.get("query", "") or "").strip()
        k = _parse_k(request.args.get("k", "8"), default=8, min_k=1, max_k=50)

        if not q:
            return jsonify({"ok": False, "error": "q (query) is required"}), 400

        mm = _get_mm()
        if mm is None:
            return jsonify({"ok": False, "error": "memory_manager not available"}), 503

        bundle = _call_flashback(mm, user=user, query=q, k=k)
        return jsonify({"ok": True, "flashback": bundle, "k": k}), 200

    except Exception as e:
        log.exception("GET /memory/flashback failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@memory_bp.get("/stats")
def memory_stats():
    try:
        mm = _get_mm()
        if mm is None:
            return jsonify({"ok": False, "error": "memory_manager not available"}), 503

        stats_fn = getattr(mm, "stats", None)
        if not callable(stats_fn):
            return jsonify({"ok": False, "error": "memory_manager.stats not available"}), 501

        s = stats_fn()
        return jsonify({"ok": True, "stats": s}), 200

    except Exception as e:
        log.exception("GET /memory/stats failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@memory_bp.post("/alias")
def memory_alias():
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        old_id = str(data.get("old_doc_id") or data.get("old_id") or "").strip()
        new_id = str(data.get("new_doc_id") or data.get("new_id") or "").strip()

        if not old_id or not new_id:
            return jsonify({"ok": False, "error": "old_doc_id and new_doc_id required"}), 400

        mm = _get_mm()
        if mm is None:
            return jsonify({"ok": False, "error": "memory_manager not available"}), 503

        res = _call_alias(mm, old_id, new_id)
        ok = bool(res.get("ok", True))  # some implementations return dist without ok
        code = 200 if ok else 400
        payload = {"ok": ok, **res}
        return jsonify(payload), code

    except Exception as e:
        log.exception("POST /memory/alias failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@memory_bp.post("/compact")
def memory_compact():
    try:
        data: Dict[str, Any] = request.get_json(silent=True) or {}
        dry = bool(data.get("dry_run", True))

        mm = _get_mm()
        if mm is None:
            return jsonify({"ok": False, "error": "memory_manager not available"}), 503

        compact_fn = getattr(mm, "compact", None)
        if not callable(compact_fn):
            return jsonify({"ok": False, "error": "memory_manager.compact not available"}), 501

        res = compact_fn(dry_run=dry)
        if isinstance(res, dict):
            ok = bool(res.get("ok", True))
            return jsonify({"ok": ok, **res}), (200 if ok else 500)

        # if the compact is not returned by dist, it still returns
        return jsonify({"ok": True, "result": res}), 200

    except Exception as e:
        log.exception("POST /memory/compact failed")
        return jsonify({"ok": False, "error": str(e)}), 500


# --------- registration ---------
def register_memory_routes(app, memory_manager, url_prefix: str = "/memory") -> None:
    """Register Blueprint i prikreplyaet memory_manager k app.

    Vazhno:
    - delaem i app.memory_manager, i app.extensions['memory_manager'] dlya sovmestimosti."""
    try:
        setattr(app, "memory_manager", memory_manager)
    except Exception:
        pass

    try:
        ext = getattr(app, "extensions", None)
        if ext is None:
            app.extensions = {}
            ext = app.extensions
        ext["memory_manager"] = memory_manager
    except Exception:
        pass

    app.register_blueprint(memory_bp, url_prefix=url_prefix)