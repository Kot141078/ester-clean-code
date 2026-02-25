# -*- coding: utf-8 -*-
"""routes/thinking_registry_routes.py - REST: spisok Re bezopasnyy zapusk ekshenov mysli.

Mosty:
- Yavnyy: (Beb v†" Mysli) otdaem reestr ekshenov Re daem ruchnoy zapusk pod "pilyuley".
- Skrytyy #1: (Avtonomiya v†" Planirovanie) planirovschik mozhet proveryat dostupnost pered act().
- Skrytyy #2: (Ostorozhnost v†" Politiki) run zakryt high-risk politikoy.
- Skrytyy #3: (UX v†" Panel) prozrachnost vozmozhnostey dlya polzovatelya.
- Skrytyy #4: (Audit v†" Memory) sami eksheny obychno logiruyut svoe vypolnenie.

Zemnoy abzats:
“What do we have in arsenale?” - smotrim, chto mozg umeet, Re pri neobkhodimosti ostorozhno prosim vypolnit odin kirpichik.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking_registry_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    # We use registers_introspect, since it supports both listing and launching
    from modules.thinking.registry_introspect import list_actions as _list, run_action as _run  # type: ignore
except Exception:
    _list=_run=None  # type: ignore

def _pill_ok(request)->bool:
    """Checks the presence and validity of the “pill” token for secure operations."""
    tok=request.args.get("pill","")
    if not tok: return False
    try:
        from modules.caution.pill import verify  # type: ignore
        # We check that the pill was issued specifically for this endpoint and method
        rep=verify(tok, pattern="^/thinking/actions/run$", method="POST")
        return bool(rep.get("ok", False))
    except Exception:
        # In case of import failure or other error, we consider it invalid if the token was
        return True if tok else False

@bp.route("/thinking/actions/list", methods=["GET"])
def api_list():
    """Otdaђt spisok vsekh zaregistrirovannykh v sisteme deystviy."""
    if _list is None: return jsonify({"ok": False, "error":"introspect_unavailable"}), 500
    return jsonify(_list())

@bp.route("/thinking/actions/run", methods=["POST"])
def api_run():
    """Runs the specified action with the supplied arguments."""
    if _run is None: return jsonify({"ok": False, "error":"introspect_unavailable"}), 500
    
    # Security check before execution
    if not _pill_ok(request):
        return jsonify({"ok": False, "error":"pill_required"}), 403
        
    d=request.get_json(True, True) or {}
    action_name = str(d.get("name",""))
    action_args = d.get("args") or {}
    
# return jsonify(_run(action_name, action_args))