# -*- coding: utf-8 -*-
"""
routes/volition_routes.py - REST-uroven dlya «pulsa voli» (volition pulse).

Endpointy:
  • GET  /volition/pulse/config    - poluchit konfig
  • POST /volition/pulse/config    - zapisat konfig (trebuetsya «pilyulya»)
  • POST /volition/pulse/tick      - vypolnit odin tik planirovschika voli (optsionalno s «pilyuley»)
  • GET  /volition/pulse/status    - status/schetchiki

Mosty:
- Yavnyy: (Veb ↔ Volya) UI/skripty/pravila mogut dergat konfig, status i tik cherez HTTP.
- Skrytyy #1: (Ostorozhnost ↔ Pilyuli) izmenenie konfiga i riskovannye tiki zaschischeny proverkoy tokena.
- Skrytyy #2: (Memory ↔ Audit) otvety determinirovany i udobny dlya zhurnalirovaniya v «profile pamyati».

Zemnoy abzats (anatomiya/inzheneriya):
Predstav «kardiomonitor» ispolnitelnosti: odna ruchka - posmotret konfiguratsiyu,
vtoraya - akkuratno ee izmenit (s zaschitoy), tretya - sdelat myagkiy shag vpered (tik).
Prosto, prozrachno i s predokhranitelem.

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_vol = Blueprint("volition_routes", __name__)

# Myagkie importy yadra «voli»
try:  # pragma: no cover
    from modules.volition.pulse import (  # type: ignore
        load_cfg as _load,
        save_cfg as _save,
        tick as _tick,
        status as _status,
    )
except Exception:  # pragma: no cover
    _load = _save = _tick = _status = None  # type: ignore

# Myagkiy import proveryayuschego «pilyulyu»
try:  # pragma: no cover
    from modules.caution.pill import verify as _verify_pill  # type: ignore
except Exception:  # pragma: no cover
    _verify_pill = None  # type: ignore


def _pill_ok(req, pattern: str) -> bool:
    """
    Proverka zaschitnoy «pilyuli» (tokena). Fail-closed: esli verifikator nedostupen - zapret.
    """
    if _verify_pill is None:
        return False
    tok = (req.args.get("pill") or "").strip()
    if not tok:
        return False
    try:
        rep = _verify_pill(tok, pattern=pattern, method=req.method)
        return bool(rep.get("ok"))
    except Exception:
        return False


def register(app) -> None:  # pragma: no cover
    app.register_blueprint(bp_vol)


def init_app(app) -> None:  # pragma: no cover
    register(app)


@bp_vol.get("/volition/pulse/config")
def api_get_cfg():
    if _load is None:
        return jsonify({"ok": False, "error": "volition_unavailable"}), 500
    try:
        cfg = _load()  # type: ignore[misc]
        return jsonify({"ok": True, "config": cfg})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vol.post("/volition/pulse/config")
def api_set_cfg():
    if _save is None:
        return jsonify({"ok": False, "error": "volition_unavailable"}), 500
    if not _pill_ok(request, pattern=r"^/volition/pulse/config$"):
        return jsonify({"ok": False, "error": "pill_required"}), 403
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    tasks = data.get("tasks")
    if tasks is None or not isinstance(tasks, list):
        return jsonify({"ok": False, "error": "bad_config"}), 400
    version = int(data.get("version", 1)) if str(data.get("version", "")).strip() else 1
    try:
        rep = _save({"version": version, "tasks": list(tasks)})  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vol.post("/volition/pulse/tick")
def api_tick():
    if _tick is None:
        return jsonify({"ok": False, "error": "volition_unavailable"}), 500
    # Pilyulya mozhet potrebovatsya dlya vnutrennikh tasks (requires_pill=true); peredaem kak est.
    pill = (request.args.get("pill") or "").strip()
    try:
        rep = _tick(pill=pill)  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp_vol.get("/volition/pulse/status")
def api_status():
    if _status is None:
        return jsonify({"ok": False, "error": "volition_unavailable"}), 500
    try:
        rep = _status()  # type: ignore[misc]
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


__all__ = ["bp_vol", "register", "init_app"]
# c=a+b


def register(app):
    app.register_blueprint(bp_vol)
    return app