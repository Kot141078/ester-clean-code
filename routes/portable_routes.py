# -*- coding: utf-8 -*-
"""
routes/portable_routes.py - HTTP-obertka poverkh self_build.

MOSTY:
- (Yavnyy) GET /portable/status - konfig portable; POST /portable/build - sobrat (dry_run=true dlya progona).
- (Skrytyy #1) Put po umolchaniyu - data/portable; vse offlayn, bez setevykh zavisimostey.
- (Skrytyy #2) Esli ukazany «neizvestnye fayly», otdaem podskazki place_unknown() dlya avto-raskladki.

ZEMNOY ABZATs:
Knopka «sobrat chemodan»: zapakovali proekt, polozhili manifest - mozhno perenosit na drugoy nositel.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.portable.self_build import build as sb_build, place_unknown
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("portable", __name__, url_prefix="/portable")

def register(app):
    app.register_blueprint(bp)

@bp.get("/status")
def status():
    base = os.getenv("PORTABLE_DIR", "data/portable")
    return jsonify({
        "ok": True,
        "dir": base,
        "include": (os.getenv("PORTABLE_INCLUDE","")),
        "exclude": (os.getenv("PORTABLE_EXCLUDE","")),
    })

@bp.post("/build")
def build():
    data: Dict[str, Any] = (request.get_json(silent=True) or {})
    dry = bool(data.get("dry_run", False))
    base = os.getenv("PORTABLE_DIR", "data/portable")
    os.makedirs(base, exist_ok=True)
    res = sb_build(base, dry_run=dry)
    return jsonify(res)

@bp.post("/classify")
def classify():
    data = (request.get_json(silent=True) or {})
    path = str(data.get("path",""))
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "error": "path not found"}), 400
    subdir, reason = place_unknown(path)
    return jsonify({"ok": True, "place_into": subdir, "reason": reason})
# c=a+b