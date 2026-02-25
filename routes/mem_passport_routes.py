# -*- coding: utf-8 -*-
"""routes/mem_passport_routes.py - REST dlya "profilenogo stola": make/upsert/list/sweep.

Mosty:
- Yavnyy: (Beb v†" Profile) edinyy vkhod dlya UI Re vneshnikh moduley.
- Skrytyy #1: (Audit v†" Servis) massovaya profileizatsiya suschestvuyuschikh dannykh (best-effort).
- Skrytyy #2: (RBAC v†" Ostorozhnost) vozmozhnost zaschitit eti ruchki politikami dostupa.
- Skrytyy #3: (Otchety v†" Prozrachnost) UI mozhet bystro pokazat, chto proiskhodilo, dlya kontrolya khronologii.

Zemnoy abzats:
Polnyy nabor knopok dlya profileizatsii: “vydat profile”, “slozhit v pamyat”, “posmotret poslednie” i “check starye zapisi”.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_passport_routes", __name__)

# Trying to import a dependency for memory access
try:
    from services.mm_access import get_mm  # type: ignore
except Exception:
    get_mm = None  # type: ignore

# Trying to import the main functions of the "passport" module
try:
    from modules.mem.passport import (
        make_passport as _make,
        upsert_with_passport as _upsert,
        list_recent as _list
    )  # type: ignore
except Exception:
    _make = _upsert = _list = None  # type: ignore

def register(app):
    """Registers this blueprint in the Flask application."""
    app.register_blueprint(bp)

@bp.route("/mem/passport/make", methods=["POST"])
def api_make():
    """Create a profile without saving it in memory."""
    if _make is None:
        return jsonify({"ok": False, "error": "passport_unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    return jsonify({
        "ok": True,
        "provenance": _make(
            str(d.get("text", "")),
            str(d.get("source", "")),
            int(d.get("version", 1))
        )
    })

@bp.route("/mem/passport/upsert", methods=["POST"])
def api_upsert():
    """Saves a profile entry to memory (creates or updates)."""
    if _upsert is None or get_mm is None:
        return jsonify({"ok": False, "error": "passport_or_mm_unavailable"}), 500
    
    d = request.get_json(True, True) or {}
    mm = get_mm()
    return jsonify(_upsert(
        mm,
        str(d.get("text", "")),
        d.get("meta") or {},
        str(d.get("source", "api://manual")),
        int(d.get("version", 1))
    ))

@bp.route("/mem/passport/sweep", methods=["POST"])
def api_sweep():
    """Best-effort: skaniruet khranilische i dobavlyaet profilea zapisyam, u kotorykh ikh net.
    Ozhidaet, chto u obekta mm budet metod iteratsii: iter(), export() or list()."""
    if get_mm is None or _upsert is None:
        return jsonify({"ok": False, "error": "passport_or_mm_unavailable"}), 500
        
    mm = get_mm()
    added = 0
    scanned = 0
    
    # Poisk dostupnogo iteratora v obekte pamyati
    it = None
    for name in ("iter", "export", "list"):
        it = getattr(mm, name, None)
        if callable(it):
            break
            
    if not callable(it):
        return jsonify({"ok": False, "error": "mm_no_iterator"})
        
    try:
        for doc in it() or []:
            scanned += 1
            meta = doc.get("meta") or {}
            # We skip entries that already have a profile
            if meta.get("provenance"):
                continue
            
            text = doc.get("text", "")
            source = meta.get("source") or "sweep://unknown"
            _upsert(mm, text, meta, source) # Using the default version
            added += 1
            
    except Exception as e:
        return jsonify({"ok": False, "error": f"sweep_error:{e}", "scanned": scanned, "added": added})
        
    return jsonify({"ok": True, "scanned": scanned, "added": added})

@bp.route("/mem/passport/list", methods=["GET"])
def api_list():
    """Returns a list of the most recently added audit profiles."""
    if _list is None:
        return jsonify({"ok": False, "error": "passport_unavailable"}), 500
    
    limit = int(request.args.get("limit", "50"))
# return jsonify(_list(limit))