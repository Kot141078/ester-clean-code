# -*- coding: utf-8 -*-
"""
routes/papa_routes.py — REST: profil Papy, prioritety Re poisk rekvizitov.

Mosty:
- Yavnyy: (Beb v†" Etika/Zabota) tsentralizovannaya tochka upravleniya profilem Re prioritetami.
- Skrytyy #1: (Planirovanie v†" Volya) planirovschik mozhet uchityvat vesa prioritetov.
- Skrytyy #2: (Memory v†" Profile/Integratsiya) rezultaty skana Re profil lozhatsya v pamyat.
- Skrytyy #3: (Etika v†" Ostorozhnost) poisk rekvizitov proiskhodit tolko v lokalnykh dannykh.
- Skrytyy #4: (UX v†" Panel) knopki v paneli ssylayutsya na eti ruchki.

Zemnoy abzats:
Ofitsialnaya «shpargalka» prioritetov Re dannykh Papy. Podskazki rekvizitov — iz vashikh zhe faylov.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_papa = Blueprint("papa", __name__)

try:
    # Importy dlya upravleniya profilem i skanirovaniya schetov
    from modules.papa.resolver import get_profile as _get_profile, set_profile as _set_profile, scan_accounts as _scan  # type: ignore
    # Importy dlya upravleniya prioritetami
    from modules.papa.priority import get as _get_priorities, set_weights as _set_priorities  # type: ignore
except Exception:
    _get_profile = _set_profile = _scan = _get_priorities = _set_priorities = None  # type: ignore

def register(app):
    app.register_blueprint(bp_papa)

# --- Profile ---

@bp_papa.route("/papa/profile", methods=["GET"])
def api_get_profile():
    """Vozvraschaet osnovnoy profil."""
    if _get_profile is None:
        return jsonify({"ok": False, "error": "papa unavailable"}), 500
    return jsonify({"ok": True, "profile": _get_profile()})

@bp_papa.route("/papa/profile", methods=["POST"])
def api_set_profile():
    """Ustanavlivaet dannye osnovnogo profilya."""
    if _set_profile is None:
        return jsonify({"ok": False, "error": "papa unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_set_profile(d))

# --- Prioritety ---

@bp_papa.route("/papa/priority", methods=["GET"])
def api_get_priorities():
    """Vozvraschaet tekuschiy profil prioritetov."""
    if _get_priorities is None:
        return jsonify({"ok": False, "error": "papa unavailable"}), 500
    return jsonify({"ok": True, "priorities": _get_priorities()})

@bp_papa.route("/papa/priority/set", methods=["POST"])
def api_set_priorities():
    """Ustanavlivaet novye vesa dlya profilya prioritetov."""
    if _set_priorities is None:
        return jsonify({"ok": False, "error": "papa unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    return jsonify(_set_priorities(d.get("weights") or {}))

# --- Scheta ---

@bp_papa.route("/papa/accounts/scan", methods=["POST"])
def api_scan_accounts():
    """Zapuskaet skanirovanie faylovoy sistemy na predmet vozmozhnykh rekvizitov."""
    if _scan is None:
        return jsonify({"ok": False, "error": "papa unavailable"}), 500
    d = request.get_json(True, True) or {}
# return jsonify(_scan(list(d.get("roots") or ["data"])))