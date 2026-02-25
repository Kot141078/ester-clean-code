# -*- coding: utf-8 -*-
"""routes/app_routes_inspect.py - REST: karta routes i proverka konfliktov.

Mosty:
- Yavnyy: (Nablyudaemost ↔ Kachestvo) vidim vse endpoints i lovim dubli.
- Skrytyy #1: (Inzheneriya ↔ Otladka) help pri massovom addavlenii novykh routov.
- Skrytyy #2: (Kibernetika ↔ Samosborka) bezopasnaya proverka pered registratsiey novykh moduley.

Zemnoy abzats:
Kak “radar”: podsvetit, where dva raza povesili odin i tot zhe put/metod.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, current_app, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_rinspect = Blueprint("app_routes_inspect", __name__)

def register(app):
    app.register_blueprint(bp_rinspect)

@bp_rinspect.route("/app/routes/map", methods=["GET"])
def api_map():
    m=[]
    for r in current_app.url_map.iter_rules():
        m.append({"rule": str(r), "endpoint": r.endpoint, "methods": sorted(list(r.methods or []))})
    return jsonify({"ok": True, "count": len(m), "items": sorted(m, key=lambda x: x["rule"])})

@bp_rinspect.route("/app/routes/verify", methods=["POST"])
def api_verify():
    seen={}
    dups=[]
    for r in current_app.url_map.iter_rules():
        key=(str(r), tuple(sorted(list(r.methods or []))))
        if key in seen:
            dups.append({"a": seen[key], "b": {"rule": str(r), "endpoint": r.endpoint}})
        else:
            seen[key]={"rule": str(r), "endpoint": r.endpoint}
    return jsonify({"ok": True, "duplicates": dups, "dup_count": len(dups)})
# c=a+b