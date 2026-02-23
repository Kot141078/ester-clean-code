# -*- coding: utf-8 -*-
"""
routes/self_replicate_routes.py - REST: snapshoty, torrent, deploy/otkat, planer avtonomii, zagruzchik.

Mosty:
- Yavnyy: (Volya ↔ Vyzhivanie) prostye ruchki: upakovat, otdat, sobrat, otkatitsya.
- Skrytyy #1: (Set ↔ Zakonnost) torrent dostupen tolko kak optsionalnyy shag; po umolchaniyu - HTTP webseed.
- Skrytyy #2: (Bezopasnost ↔ Kontrol) approve/rollback podchinyayutsya globalnym pravilam (high-risk → «tabletka»).

Zemnoy abzats:
Eto «nabor instrumentov vyzhivaniya»: upakovat sebya, podelitsya legalno, sobrat snova, a esli chto - otkatitsya.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, request, send_from_directory
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_selfx = Blueprint("self_replicate", __name__)

try:
    from modules.self.archiver import create_snapshot, list_snapshots, build_torrent  # type: ignore
    from modules.self.deployer import stage as _stage, approve as _approve, rollback as _rollback  # type: ignore
    from modules.self.autonomy import plan as _plan, execute as _exec  # type: ignore
except Exception:
    create_snapshot = list_snapshots = build_torrent = None  # type: ignore
    _stage = _approve = _rollback = None  # type: ignore
    _plan = _exec = None  # type: ignore

def register(app):
    app.register_blueprint(bp_selfx)

# - snapshots -
@bp_selfx.route("/self/pack/snapshot", methods=["POST"])
def api_snapshot():
    if create_snapshot is None: return jsonify({"ok": False, "error":"archiver unavailable"}), 500
    note = (request.get_json(True, True) or {}).get("note","")
    return jsonify(create_snapshot(note=note))

@bp_selfx.route("/self/pack/list", methods=["GET"])
def api_list():
    if list_snapshots is None: return jsonify({"ok": False, "error":"archiver unavailable"}), 500
    return jsonify(list_snapshots())

@bp_selfx.route("/self/pack/download/<path:name>", methods=["GET"])
def api_download(name: str):
    snap_dir = os.getenv("SELF_SNAPSHOT_DIR","data/self/snapshots")
    return send_from_directory(snap_dir, name, as_attachment=True)

@bp_selfx.route("/self/pack/torrent", methods=["POST"])
def api_torrent():
    if build_torrent is None: return jsonify({"ok": False, "error":"archiver unavailable"}), 500
    d = request.get_json(True, True) or {}
    arch = str(d.get("archive") or "")
    webseed = str(d.get("webseed_url") or "")
    return jsonify(build_torrent(arch, webseed_url=webseed or None))

# - deploy -
@bp_selfx.route("/self/deploy/stage", methods=["POST"])
def api_stage():
    if _stage is None: return jsonify({"ok": False, "error":"deployer unavailable"}), 500
    d = request.get_json(True, True) or {}
    files = d.get("files") or {}
    reason = str(d.get("reason",""))
    return jsonify(_stage(files, reason))

@bp_selfx.route("/self/deploy/approve", methods=["POST"])
def api_approve():
    if _approve is None: return jsonify({"ok": False, "error":"deployer unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_approve(str(d.get("stage_id","")), bool(d.get("pill", False))))

@bp_selfx.route("/self/deploy/rollback", methods=["POST"])
def api_rollback():
    if _rollback is None: return jsonify({"ok": False, "error":"deployer unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_rollback(str(d.get("snapshot_archive",""))))

# - autonomy -
@bp_selfx.route("/self/autonomy/plan", methods=["POST"])
def api_plan():
    if _plan is None: return jsonify({"ok": False, "error":"autonomy unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_plan(str(d.get("goal","replicate"))))

@bp_selfx.route("/self/autonomy/execute", methods=["POST"])
def api_exec():
    if _exec is None: return jsonify({"ok": False, "error":"autonomy unavailable"}), 500
    d = request.get_json(True, True) or {}
    return jsonify(_exec(d.get("plan") or {}))
# c=a+b