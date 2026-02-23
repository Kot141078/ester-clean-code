# -*- coding: utf-8 -*-
"""
routes/imprint_routes.py — REST: imprint Papy (set/status/verify/canon).

Mosty:
- Yavnyy: (Beb v†" Etika/Goverie) dostup k kanonu Re ego proverke iz UI/skriptov.
- Skrytyy #1: (Integratsiya v†" Release) imprint vklyuchaetsya v snepshoty.
- Skrytyy #2: (Memory v†" Invarianty) kanon ne khranitsya v VD, a vshit v kod.
- Skrytyy #3: (Bezopasnost v†" Politiki) mozhno trebovat rol admin dlya /imprint/set.

Zemnoy abzats:
«Znay Re ne iskay iskazheniy» — odin POST, Re vidno, ne podmenili li slova Papy.
Prostye ruchki dlya ustanovki, polucheniya statusa, kanona i proverki imprinta.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_imprint = Blueprint("imprint_routes", __name__)

try:
    # Obedinennyy import vsekh neobkhodimykh funktsiy
    from modules.self.imprint import set_imprint as _set, status as _status, verify as _verify, canon as _canon  # type: ignore
except Exception:
    # Obrabotka oshibki, esli modul nedostupen
    _set=_status=_verify=_canon=None  # type: ignore

def register(app):
    app.register_blueprint(bp_imprint)

@bp_imprint.route("/imprint/status", methods=["GET"])
def api_status():
    """Vozvraschaet tekuschiy status imprinta."""
    if _status is None: return jsonify({"ok": False, "error":"imprint_unavailable"}), 500
    return jsonify(_status())

@bp_imprint.route("/imprint/set", methods=["POST"])
def api_set():
    """Ustanavlivaet novyy tekst imprinta."""
    if _set is None: return jsonify({"ok": False, "error":"imprint_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_set(str(d.get("text",""))))

@bp_imprint.route("/imprint/verify", methods=["POST"])
def api_verify():
    """Proveryaet tekst i khesh imprinta."""
    if _verify is None: return jsonify({"ok": False, "error":"imprint_unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_verify(d.get("text"), d.get("sha256")))

@bp_imprint.route("/imprint/canon", methods=["GET"])
def api_canon():
    """Vozvraschaet kanonicheskiy tekst Re khesh imprinta."""
    if _canon is None: return jsonify({"ok": False, "error":"imprint_unavailable"}), 500
# return jsonify(_canon())