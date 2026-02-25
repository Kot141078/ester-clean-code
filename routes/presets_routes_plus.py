# -*- coding: utf-8 -*-
"""routes/presets_routes_plus.py - Rasshirennye routey dlya presetov (baza + extra).

MOSTY:
- (Yavnyy) /presetsx/list i /presetsx/compose chitayut bazovye PRESETS i PRESETS_EXTRA.
- (Skrytyy #1) Ne menyaet suschestvuyuschie /presets/* - vse drop-in; mozhno ispolzovat both API.
- (Skrytyy #2) Pryamaya integratsiya s audience_infer (optsionalno) - avtopodbor auditorii pri compose.

ZEMNOY ABZATs:
Pozvolyaet dobavlyat presety bez pravok ranee vydannykh faylov, sokhranyaya stabilnost kontrakta.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, request, jsonify

from modules.presets.letter_templates import PRESETS as BASE_PRESETS
from modules.presets.bank_extras import PRESETS_EXTRA
from modules.audience_infer import infer_audience
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("presets_routes_plus", __name__, url_prefix="/presetsx")

def _merged():
    m = dict(BASE_PRESETS)
    m.update(PRESETS_EXTRA)
    return m

@bp.route("/list", methods=["GET"])
def list_all():
    P = _merged()
    groups = {}
    for key in sorted(P.keys()):
        group, name = key.split(".", 1)
        groups.setdefault(group, []).append(name)
    return jsonify({"ok": True, "groups": groups, "count": len(P)})

@bp.route("/compose", methods=["POST"])
def compose():
    """
    body: { preset: "...", facts: {...}, meta?: {...}, auto_audience?: bool }
    -> { ok, preset, audience?, confidence?, text }
    """
    j = request.get_json(force=True, silent=True) or {}
    preset = (j.get("preset") or "").strip()
    facts: Dict[str, Any] = j.get("facts") or {}
    meta: Dict[str, Any] = j.get("meta") or {}
    auto = bool(j.get("auto_audience", False))

    P = _merged()
    if preset not in P:
        return jsonify({"ok": False, "error": "unknown_preset"}), 400
    try:
        text = P[preset](facts)
    except Exception as e:
        return jsonify({"ok": False, "error": "compose_failed", "detail": str(e)}), 400

    # Optionally - an attempt to determine the audience for the further route
    audience = None; conf = None
    if auto:
        audience, conf = infer_audience(meta=meta, text=text)

    return jsonify({"ok": True, "preset": preset, "text": text, "audience": audience, "confidence": conf})

def register(app):
    app.register_blueprint(bp)
    return bp