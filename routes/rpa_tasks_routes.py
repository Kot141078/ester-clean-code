# -*- coding: utf-8 -*-
"""routes/rpa_tasks_routes.py - REST dlya makrosov RPA (mysli → deystviya).

Ruchki:
  GET /desktop/rpa/macro/list -> {ok, items:[...]}
  POST /desktop/rpa/macro/run {"name": "...", "args": {...}} -> {ok, ...}

Require rol JWT: operator (sm. security/rbac_utils.require_role).
Dlya lokalnoy otladki mozhno vystavit ENV RPA_RBAC_DISABLE=1.

MOSTY:
- Yavnyy: (Plan ↔ Akt) mysli (makrosy) zapuskayutsya kak HTTP-zadachi.
- Skrytyy #1: (Infoteoriya ↔ Bezopasnost) RBAC ogranichivaet alfavit deystviy po rolyam.
- Skrytyy #2: (Kibernetika ↔ Audit) makrosy ispolzuyut uzhe logiruemye /desktop/rpa/* → edinyy zhurnal.

ZEMNOY ABZATs:
Daet Ester i operatoru “pult stsenariev”: ot prostykh do sostavnykh deystviy,
ne menyaya nizkourovnevye kontrakty.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict

from modules.thinking.rpa_macros import list_macros, run_macro, MacroError
from security.rbac_utils import require_role
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_rpa_tasks", __name__, url_prefix="/desktop/rpa/macro")

@bp.route("/list", methods=["GET"])
@require_role("operator")
def macro_list():
    return jsonify({"ok": True, "items": list_macros()})

@bp.route("/run", methods=["POST"])
@require_role("operator")
def macro_run():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    args = data.get("args") or {}
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    try:
        res = run_macro(name, args)
        res.update(ok=True, name=name)
        return jsonify(res)
    except MacroError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"exception:{e}"}), 500

def register(app):
    app.register_blueprint(bp)