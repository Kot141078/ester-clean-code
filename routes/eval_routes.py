# -*- coding: utf-8 -*-
"""
routes/eval_routes.py - REST: spisok i zapusk minimalnykh regress-testov.

Mosty:
- Yavnyy: (Operatsii ↔ Kachestvo) bystryy progon pered opasnymi izmeneniyami.
- Skrytyy #1: (Kontrol ↔ Prozrachnost) rezultaty v JSON, udobno integrirovat v UI/skripty.
- Skrytyy #2: (Vyzhivanie ↔ Otkat) ne proshli - ne deploim.

Zemnoy abzats:
Pered tem kak krutit «bolshoy rubilnik», ubedis, chto zelenoe - zelenoe.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict, List
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_eval = Blueprint("eval", __name__)

try:
    from modules.eval.bench import list_tests, run  # type: ignore
except Exception:
    list_tests = run = None  # type: ignore

def register(app):
    app.register_blueprint(bp_eval)

@bp_eval.route("/eval/list", methods=["GET"])
def api_list():
    if list_tests is None: return jsonify({"ok": False, "error":"eval unavailable"}), 500
    return jsonify({"ok": True, "tests": list_tests()})

@bp_eval.route("/eval/run", methods=["POST"])
def api_run():
    if run is None: return jsonify({"ok": False, "error":"eval unavailable"}), 500
    d: Dict[str, Any] = request.get_json(True, True) or {}
    names = d.get("names")
    return jsonify(run(names if isinstance(names, list) else None))
# c=a+b