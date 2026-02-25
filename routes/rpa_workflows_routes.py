# -*- coding: utf-8 -*-
"""routes/rpa_workflows_routes.py - REST dlya workflow i oflayn-planirovschika.

Ruchki:
  GET /desktop/rpa/workflow/list
  GET /desktop/rpa/workflow/get?name=...
  POST /desktop/rpa/workflow/save {"name": "...", "spec": {...}}
  POST /desktop/rpa/workflow/run {"name": "...", "args_overrides": {...}}
  POST /desktop/rpa/workflow/export {"names": ["..."]} -> {"ok":true,"bundle":{name:spec,...}}
  POST /desktop/rpa/workflow/import {"bundle": {name:spec,...}}
  GET /desktop/rpa/schedule/list
  POST /desktop/rpa/schedule/save {"items":[{name,interval_sec,enabled,last_ts?},...]}
  POST /desktop/rpa/schedule/tick

RBAC: rol 'operator' (lokalnyy JWT) - sm. security/rbac_utils.require_role.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request

from security.rbac_utils import require_role
from modules.thinking.rpa_workflows import (
    list_workflows,
    load_workflow,
    save_workflow,
    run_workflow,
    sched_list,
    sched_save,
    sched_tick,
)

bp = Blueprint("desktop_rpa_workflows", __name__, url_prefix="/desktop/rpa")

@bp.route("/workflow/list", methods=["GET"])
@require_role("operator")
def wf_list():
    return jsonify({"ok": True, "items": list_workflows()})

@bp.route("/workflow/get", methods=["GET"])
@require_role("operator")
def wf_get():
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    try:
        spec = load_workflow(name)
        return jsonify({"ok": True, "spec": spec})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "workflow_not_found"}), 404

@bp.route("/workflow/save", methods=["POST"])
@require_role("operator")
def wf_save():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    spec = data.get("spec") or {}
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    try:
        save_workflow(name, spec)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/workflow/run", methods=["POST"])
@require_role("operator")
def wf_run():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    overrides = data.get("args_overrides") or {}
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    res = run_workflow(name, overrides)
    return jsonify(res), (200 if res.get("ok") else 400)

@bp.route("/workflow/export", methods=["POST"])
@require_role("operator")
def wf_export():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    names = data.get("names") or []
    bundle: Dict[str, Any] = {}
    for n in names:
        try:
            bundle[n] = load_workflow(n)
        except FileNotFoundError:
            pass
    return jsonify({"ok": True, "bundle": bundle})

@bp.route("/workflow/import", methods=["POST"])
@require_role("operator")
def wf_import():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    bundle: Dict[str, Any] = data.get("bundle") or {}
    for name, spec in bundle.items():
        save_workflow(name, spec)
    return jsonify({"ok": True, "count": len(bundle)})

@bp.route("/schedule/list", methods=["GET"])
@require_role("operator")
def sch_list():
    return jsonify({"ok": True, "items": sched_list()})

@bp.route("/schedule/save", methods=["POST"])
@require_role("operator")
def sch_save():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    items = data.get("items") or []
    try:
        sched_save(items)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@bp.route("/schedule/tick", methods=["POST"])
@require_role("operator")
def sch_tick():
    res = sched_tick(None)
    return jsonify(res)
    
def register(app):
    app.register_blueprint(bp)
