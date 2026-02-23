# -*- coding: utf-8 -*-
"""
routes/mentor_to_workflow_routes.py - eksport plana «Nastavnika» v JSON-workflow.

Ruchka:
  POST /mentor/export_workflow {"text":"pokazhi kak polzovatsya notepad","name":"teach_notepad"}

Pravila meppinga:
- focus/rpa.open(app) -> step macro "open_portal_and_type" {app, text:""}
- click (esli byl box/template) -> "click_xy" {x,y} - koordinaty nuzhno peredat (esli zaranee nashli)
- type/rpa.type(text) -> "type_text" {text}
- info -> propuskaem

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict, List

from modules.thinking.mentor_planner import plan_from_request
from modules.thinking.rpa_workflows import save_workflow
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mentor_to_workflow", __name__, url_prefix="/mentor")

@bp.route("/export_workflow", methods=["POST"])
def export_workflow():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    name = (data.get("name") or "").strip() or "mentor_workflow"
    plan = plan_from_request(text)
    steps: List[Dict[str, Any]] = []
    for st in plan.get("steps", []):
        t = st.get("type")
        if t == "focus":
            act = st.get("action") or {}
            if act.get("type") == "rpa.open":
                steps.append({"macro":"open_portal_and_type","args":{"app":act.get("app",""),"text":""}})
        elif t == "type":
            act = st.get("action") or {}
            if act.get("type") == "rpa.type":
                steps.append({"macro":"type_text","args":{"text":act.get("text","")}})
        elif t == "click":
            if "box" in st:
                b = st["box"]; steps.append({"macro":"click_xy","args":{"x":int(b["left"])+int(b["width"])//2,"y":int(b["top"])+int(b["height"])//2}})
        # info - propuskaem
    spec = {"name": name, "steps": steps}
    try:
        save_workflow(name, spec)
        return jsonify({"ok": True, "workflow": name, "steps": len(steps)})
    except Exception as e:
        return jsonify({"ok": False, "error": f"save_failed:{e}"}), 400

def register(app):
    app.register_blueprint(bp)