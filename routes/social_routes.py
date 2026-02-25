# -*- coding: utf-8 -*-
"""routes/social_routes.py - REST: kampanii, upload-kit, ledzher.

Mosty:
- Yavnyy: (Veb ↔ Sotsseti) sozdaem kampanii, plany, sborki kitov i vedem uchet.
- Skrytyy #1: (Studiya ↔ Sotskit) nakhodim assety studii avtomaticheski.
- Skrytyy #2: (Memory ↔ Profile) vse klyuchevye sobytiya logiruyutsya v pamyat modulyami.

Zemnoy abzats:
Knopki “sozdat kampaniyu”, “sobrat kit”, “zapisat prosmotry/dokhod” - polnyy tsikl pod rukoy.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, glob, json
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("social_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.social.campaign import create as _create, plan as _plan, get as _get  # type: ignore
    from modules.social.kit import build as _build  # type: ignore
    from modules.social.ledger import record as _record, list_all as _list  # type: ignore
except Exception:
    _create=_plan=_get=_build=_record=_list=None  # type: ignore

@bp.route("/social/campaign/create", methods=["POST"])
def api_create():
    if _create is None: return jsonify({"ok": False, "error":"social_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_create(str(d.get("title","Campaign")), str(d.get("goal","awareness"))))

@bp.route("/social/campaign/plan", methods=["POST"])
def api_plan():
    if _plan is None: return jsonify({"ok": False, "error":"social_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_plan(str(d.get("id","")), dict(d.get("sources") or {}), list(d.get("platforms") or []), list(d.get("tags") or [])))

@bp.route("/social/kit/build", methods=["POST"])
def api_build():
    if _build is None: return jsonify({"ok": False, "error":"social_unavailable"}), 500
    d=request.get_json(True, True) or {}
    cid=str(d.get("id",""))
    # if champaign is specified - take its last plan as asset default
    assets = d.get("assets")
    if cid and not assets and _get is not None:
        c=_get(cid)
        if c.get("ok"):
            plans=c["campaign"].get("plans") or []
            if plans: assets=plans[0].get("assets")
    return jsonify(_build(str(d.get("platform","tiktok")), str(d.get("title","Untitled")), str(d.get("description","")), list(d.get("tags") or []), dict(assets or {}), d.get("schedule_ts")))

@bp.route("/social/exports", methods=["GET"])
def api_exports():
    root=os.getenv("SOCIAL_OUT","data/social/out")
    files=sorted(glob.glob(os.path.join(root,"kit_*")))
    return jsonify({"ok": True, "kits": files})

@bp.route("/social/ledger/record", methods=["POST"])
def api_record():
    if _record is None: return jsonify({"ok": False, "error":"social_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_record(str(d.get("platform","")), str(d.get("campaign","")), str(d.get("metric","views")), float(d.get("value",0.0)), str(d.get("currency","")), dict(d.get("extra") or {})))

@bp.route("/social/ledger/list", methods=["GET"])
def api_list():
    if _list is None: return jsonify({"ok": False, "error":"social_unavailable"}), 500
    return jsonify(_list())
# c=a+b