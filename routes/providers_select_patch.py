# -*- coding: utf-8 -*-
"""
routes/providers_select_patch.py

Naznachenie:
- Dobavit nedostayuschiy marshrut vybora provaydera:
    POST /providers/select  {"provider":"openai"} | {"name":"lmstudio"}
- Zapis idet v data/app/providers/active.json (bez JWT, chtoby uprostit CLI).

Mosty (skrytye):
(1) Vybor → persistent-fayl → chitaetsya vsemi uzlami.
(2) Sovmestimost s uzhe suschestvuyuschim /providers/status.

Zemnoy abzats:
Eto kak pereklyuchit «vkhod» na pulte audiousilitelya — zapis odnoy ruchkoy,
a vidyat ee vse komponenty trakta.

c=a+b
"""
from __future__ import annotations
import os, json
from pathlib import Path
from flask import Blueprint, jsonify, request
try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn):
            return fn
        return _wrap
try:
    from modules.auth.rbac import has_any_role as _has_any_role
except Exception:
    def _has_any_role(_required):  # type: ignore
        return True
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_select_patch", __name__)

def _data_root() -> Path:
    return Path(os.environ.get("ESTER_DATA_ROOT") or os.environ.get("ESTER_DATA_DIR") or (Path.cwd() / "data"))

def _active_path() -> Path:
    p = _data_root() / "app" / "providers"
    p.mkdir(parents=True, exist_ok=True)
    return p / "active.json"

@bp.post("/providers/select")
@jwt_required()
def providers_select():
    if not _has_any_role(["provider_manager", "admin"]):
        return jsonify({"ok": False, "error": "rbac deny"}), 403
    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or data.get("name") or "").strip().lower()
    if not provider:
        return jsonify({"ok": False, "error": "provider_required"}), 400
    payload = {"active": provider, "provider": provider, "name": provider}
    _active_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "active": provider})

def register(app):
    app.register_blueprint(bp)
    return app
