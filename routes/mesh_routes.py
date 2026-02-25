# -*- coding: utf-8 -*-
"""routes/mesh_routes.py - REST: sposobnosti uzla i ochered zadach (submit/claim/heart/finish/pull/list).

Mosty:
- Yavnyy: (Veb ↔ Mesh) daet frontu i “vole” polnyy kontrol nad zadachami uzla.
- Skrytyy #1: (P2P ↔ Dedup) dergaet Bloom-filtr v ocheredi.
- Skrytyy #2: (Backpressure ↔ Ostorozhnost) sovmestimo s ingest.guard.* pered vneshnim setevym pull.

Zemnoy abzats:
Panel “sister”: what ya umeyu i kakie zakazy v ocheredi - vzyat, prodlit, sdat, podtyanut u sosedey.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("mesh_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.mesh.capabilities import capabilities as _caps  # type: ignore
    from modules.mesh.task_queue import submit as _sub, claim as _cl, heartbeat as _hb, finish as _fin, list_tasks as _ls, pull_from_peers as _pull  # type: ignore
except Exception:
    _caps=_sub=_cl=_hb=_fin=_ls=_pull=None  # type: ignore

@bp.route("/mesh/capabilities", methods=["GET"])
def api_caps():
    if _caps is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    return jsonify(_caps())

@bp.route("/mesh/task/submit", methods=["POST"])
def api_submit():
    if _sub is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_sub(str(d.get("kind","")), dict(d.get("payload") or {})))

@bp.route("/mesh/task/claim", methods=["POST"])
def api_claim():
    if _cl is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_cl(str(d.get("worker","anon")), list(d.get("kinds") or []), int(d.get("lease_sec",300))))

@bp.route("/mesh/task/heartbeat", methods=["POST"])
def api_heartbeat():
    if _hb is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_hb(str(d.get("id","")), int(d.get("extend_sec",300))))

@bp.route("/mesh/task/finish", methods=["POST"])
def api_finish():
    if _fin is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_fin(str(d.get("id","")), bool(d.get("success",True)), dict(d.get("result") or {})))

@bp.route("/mesh/task/pull", methods=["POST"])
def api_pull():
    if _pull is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_pull(list(d.get("peers") or []), int(d.get("max_items",20))))

@bp.route("/mesh/task/list", methods=["GET"])
def api_list():
    if _ls is None: return jsonify({"ok": False, "error":"mesh_unavailable"}), 500
    return jsonify(_ls())
# c=a+b