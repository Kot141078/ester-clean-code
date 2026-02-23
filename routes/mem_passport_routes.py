# -*- coding: utf-8 -*-
"""
routes/mem_passport_routes.py — REST dlya «profilenogo stola»: make/upsert/list/sweep.

Mosty:
- Yavnyy: (Beb v†" Profile) edinyy vkhod dlya UI Re vneshnikh moduley.
- Skrytyy #1: (Audit v†" Servis) massovaya profileizatsiya suschestvuyuschikh dannykh (best-effort).
- Skrytyy #2: (RBAC v†" Ostorozhnost) vozmozhnost zaschitit eti ruchki politikami dostupa.
- Skrytyy #3: (Otchety v†" Prozrachnost) UI mozhet bystro pokazat, chto proiskhodilo, dlya kontrolya khronologii.

Zemnoy abzats:
Polnyy nabor knopok dlya profileizatsii: «vydat profile», «slozhit v pamyat», «posmotret poslednie» i «proverit starye zapisi».

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mem_passport_routes", __name__)

# Popytka importirovat zavisimost dlya dostupa k pamyati
try:
    from services.mm_access import get_mm  # type: ignore
except Exception:
    get_mm = None  # type: ignore

# Popytka importirovat osnovnye funktsii modulya "passport"
try:
    from modules.mem.passport import (
        make_passport as _make,
        upsert_with_passport as _upsert,
        list_recent as _list
    )  # type: ignore
except Exception:
    _make = _upsert = _list = None  # type: ignore

def register(app):
    """R egistriruet etot blueprint v prilozhenii Flask."""
    app.register_blueprint(bp)

@bp.route("/mem/passport/make", methods=["POST"])
def api_make():
    """Sozdaђt profile, ne sokhranyaya ego v pamyati."""
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
    """Sokhranyaet zapis s profileom v pamyat (sozdaet ili obnovlyaet)."""
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
    """
    Best-effort: skaniruet khranilische i dobavlyaet profilea zapisyam, u kotorykh ikh net.
    Ozhidaet, chto u obekta mm budet metod iteratsii: iter(), export() ili list().
    """
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
            # Propuskaem zapisi, u kotorykh uzhe est profile
            if meta.get("provenance"):
                continue
            
            text = doc.get("text", "")
            source = meta.get("source") or "sweep://unknown"
            _upsert(mm, text, meta, source) # Ispolzuem versiyu po umolchaniyu
            added += 1
            
    except Exception as e:
        return jsonify({"ok": False, "error": f"sweep_error:{e}", "scanned": scanned, "added": added})
        
    return jsonify({"ok": True, "scanned": scanned, "added": added})

@bp.route("/mem/passport/list", methods=["GET"])
def api_list():
    """Vozvraschaet spisok poslednikh dobavlennykh profileov dlya audita."""
    if _list is None:
        return jsonify({"ok": False, "error": "passport_unavailable"}), 500
    
    limit = int(request.args.get("limit", "50"))
# return jsonify(_list(limit))