# -*- coding: utf-8 -*-
"""routes/providers_models.py - spisok/vybor modeli.

MOSTY:
- (Yavnyy) GET /providers/models - LM Studio /v1/models (+ vybrannaya).
- (Skrytyy #1) POST /ui/model {"model":"..."} - sokhranyaet vybor v data/runtime/model.txt.
- (Skrytyy #2) Ne lomaet suschestvuyuschie provaydery - eto lish podskazka registry.

ZEMNOY ABZATs:
Tumbler “kakim golosom dumaem”: vybral model - dalshe ves UI rabotaet cherez nee.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.providers.lmstudio_models import list_models, get_preferred_model, set_preferred_model
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("providers_models", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.get("/providers/models")
def models():
    lst = list_models()
    return jsonify({"ok": True, "models": lst, "preferred": get_preferred_model()})

@bp.post("/ui/model")
def set_model():
    data = request.get_json(silent=True) or {}
    model = (data.get("model") or "").strip()
    if not model:
        return jsonify({"ok": False, "error": "model required"}), 400
    ok = set_preferred_model(model)
    return jsonify({"ok": ok, "model": model})
# c=a+b