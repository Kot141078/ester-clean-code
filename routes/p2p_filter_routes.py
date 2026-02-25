# -*- coding: utf-8 -*-
"""routes/p2p_filter_routes.py - REST dlya Filtra Bluma P2P: add/check/status/stats/import/export/sync.

Mosty:
- Yavnyy: (Veb ↔ P2P) obmenivatsya sostoyaniem filtra dlya bystroy sinkhronizatsii uzlov i predotvrascheniya dubley.
- Skrytyy #1: (Privatnost ↔ Ekonomiya) po seti peredayutsya tolko bity, a ne sami dokumenty - ekonomim trafik i ne raskryvaem soderzhimoe.
- Skrytyy #2: (Konsensus ↔ Deduplikatsiya) prostoy protokol pozvolyaet bystro proveryat nalichie dannykh u partnera i snizhat izbytochnost.
- Skrytyy #3: (Profile ↔ Audit) sostoyanie filtra udobno dlya sbora metrik setevogo vzaimodeystviya.

Zemnoy abzats:
Eto kak obschaya “kartoteka otmetok”: prezhde chem otpravit chto-to v set, sprashivaem filtr - ne videli li uzhe takoy ID.
Mozhno obmenivatsya nalichiem dannykh (kak “otmetkami” o prochitannykh knigakh), ne raskryvaya ikh i ne sozdavaya lishniy noise.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_filter_routes", __name__)


def register(app):  # pragma: no cover
    """Registriruet dannyy Blueprint v prilozhenii Flask."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


# Soft import of the Bloom filter core
try:
    from modules.p2p.bloom import (  # type: ignore
        add as _add,
        check as _check,
        export_state as _export,
        import_state as _import,
        stats as _stats,
        status as _status,
    )
except Exception:  # pragma: no cover
    _add = _check = _export = _import = _stats = _status = None  # type: ignore


@bp.route("/p2p/filter/status", methods=["GET"])
def api_status():
    """Returns the current status of the P2P filter (simple availability check)."""
    if _status is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    try:
        res = _status()
        if isinstance(res, dict):
            return jsonify(res)
        return jsonify({"ok": True, "status": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/stats", methods=["GET"])
def api_stats():
    """Returns detailed statistics on the P2P filter."""
    if _stats is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    try:
        res = _stats()
        return jsonify(res if isinstance(res, dict) else {"ok": True, "stats": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/check", methods=["POST"])
def api_check():
    """Checks which of the passed IDs are already in the filter."""
    if _check is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "ids must be a list"}), 400
    try:
        return jsonify(_check(list(ids)))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/add", methods=["POST"])
def api_add():
    """Dobavlyaet (anonsiruet) spisok ID v filtr."""
    if _add is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "ids must be a list"}), 400
    try:
        return jsonify(_add(list(ids)))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/export_state", methods=["GET"])
def api_export_state():
    """Exports the full filter state (m, k, bic) for quick synchronization."""
    if _export is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    try:
        return jsonify(_export())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/import_state", methods=["POST"])
def api_import_state():
    """Imports and sets the complete filter state from the passed data."""
    if _import is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        m = int(d.get("m", 0))
        k = int(d.get("k", 0))
        bits = str(d.get("bits", ""))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "m, k must be integers; bits must be string"}), 400
    try:
        return jsonify(_import(m, k, bits))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/p2p/filter/sync_ids", methods=["POST"])
def api_sync_ids():
    """Kompleksnaya sinkhronizatsiya: partner prisylaet svoi ID.
    Funktsiya proveryaet, kakie iz nikh novye, dobavlyaet vse v lokalnyy filtr
    i vozvraschaet detalnyy otchet o sostoyanii do i after."""
    if _add is None or _check is None:
        return jsonify({"ok": False, "error": "p2p_unavailable"}), 500

    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "ids must be a list"}), 400

    if not ids:
        return jsonify({"ok": True, "message": "no ids provided for sync"})

    try:
        before_check_report = _check(list(ids))
        add_report = _add(list(ids))
        after_check_report = _check(list(ids))
        return jsonify(
            {
                "ok": True,
                "before": before_check_report,
                "added": add_report,
                "after": after_check_report,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp", "register", "init_app"]
# c=a+b