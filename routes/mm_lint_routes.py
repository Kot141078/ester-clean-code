# -*- coding: utf-8 -*-
"""routes/mm_lint_routes.py - REST: zapusk linta get_mm().

Mosty:
- Yavnyy: (Veb ↔ Lint) bystryy otchet po obkhodam fabriki pamyati.
- Skrytyy #1: (Plan ↔ Ispravleniya) rezultat sokhranyaetsya na disk dlya posleduyuschey raboty.
- Skrytyy #2: (Profile ↔ Audit) pri zhelanii mozhno dopisat zapis profilea.

Zemnoy abzats:
Nazhali “proverit” - poluchili spisok faylov, where pamyat podklyuchayut napryamuyu: vidno, where podtyanut distsiplinu.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mm_lint_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.dev.mm_lint import run as _run  # type: ignore
except Exception:
    _run=None  # type: ignore

@bp.route("/dev/mm_lint/run", methods=["GET"])
def api_run():
    if _run is None: return jsonify({"ok": False, "error":"mm_lint_unavailable"}), 500
    return jsonify(_run())
# c=a+b