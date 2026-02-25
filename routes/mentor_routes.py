# -*- coding: utf-8 -*-
"""routes/mentor_routes.py - rezhim “Nastavnik”: plan shagov, podsvetka i ispolnenie.

Ruchki:
  POST /mentor/plan {"text":"pokazhi kak polzovatsya notepad"} -> {ok, name, steps}
  POST /mentor/overlay {"step":{"type":"click","template_b64":...,"ocr":"OK","title":"Nazhmi OK"}} -> {ok, overlay_b64, box?}
  POST /mentor/exec {"step":{...}} -> {ok}

Igrovye window:
  GET /mentor/game/priorities
  POST /mentor/game/priorities {"items":[{"title":"Diablo","priority":10}]}
  POST /mentor/game/focus

Dependency: /desktop/rpa/screen, /desktop/rpa/click, /desktop/rpa/type, vision.template_match, window ops.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict
import http.client, json

from modules.thinking.mentor_planner import plan_from_request
from modules.vision.template_match import find as tmpl_find
from modules.vision.overlay import draw_box_label, draw_arrow
from modules.ops.window_priority import get_list as pr_get, save_list as pr_save, pick_focus as pr_pick
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("mentor_routes", __name__, url_prefix="/mentor")

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("GET", path)
    r = conn.getresponse()
    data = r.read().decode("utf-8","ignore")
    conn.close()
    try: return json.loads(data)
    except Exception: return {"ok": False, "raw": data}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    data = r.read().decode("utf-8","ignore")
    conn.close()
    try: return json.loads(data)
    except Exception: return {"ok": False, "raw": data}

@bp.route("/plan", methods=["POST"])
def mentor_plan():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    return jsonify(plan_from_request(text))

@bp.route("/overlay", methods=["POST"])
def mentor_overlay():
    data = request.get_json(force=True, silent=True) or {}
    step = data.get("step") or {}
    screen = _get("/desktop/rpa/screen")
    if not screen.get("ok"):
        return jsonify({"ok": False, "error": "screen_failed"}), 500
    png = screen["png_b64"]

    # if there is a template, we will find and draw a frame
    tb64 = (step.get("template_b64") or "").strip()
    if tb64:
        res = tmpl_find(png, tb64, float(step.get("threshold") or 0.78))
        if res.get("ok"):
            label = step.get("title") or "Shag"
            ov = draw_box_label(png, res["box"], label)
            return jsonify({"ok": True, "overlay_b64": ov, "box": res["box"], "score": res.get("score")})
        else:
            return jsonify({"ok": False, "error": "template_not_found", "score": res.get("score",0.0)}), 404

    # otherwise - just an arrow from the center to a conditional point (stub)
    ov = draw_arrow(png, (40, 40), (200, 120), step.get("title") or "Shag")
    return jsonify({"ok": True, "overlay_b64": ov})

@bp.route("/exec", methods=["POST"])
def mentor_exec():
    data = request.get_json(force=True, silent=True) or {}
    step = data.get("step") or {}
    t = (step.get("type") or "").lower()
    # focus/open
    if t == "focus":
        act = step.get("action") or {}
        if act.get("type") == "rpa.open":
            return jsonify(_post("/desktop/rpa/open", {"app": act.get("app")})), 200
        if act.get("type") == "window.focus":
            # we already have a universal title handle
            return jsonify(_post("/desktop/window/focus", {"title": act.get("title")})), 200
        return jsonify({"ok": True})
    # click
    if t == "click":
        # if you found a boxing center in advance; otherwise we'll try using the template
        if step.get("box"):
            b = step["box"]; cx, cy = b["left"]+b["width"]//2, b["top"]+b["height"]//2
            return jsonify(_post("/desktop/rpa/click", {"x": cx, "y": cy})), 200
        if step.get("template_b64"):
            scr = _get("/desktop/rpa/screen")
            res = tmpl_find(scr.get("png_b64",""), step["template_b64"], float(step.get("threshold") or 0.78))
            if res.get("ok"):
                c = res["center"]; return jsonify(_post("/desktop/rpa/click", {"x": c["x"], "y": c["y"]})), 200
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": False, "error": "no_target"}), 400
    # type
    if t == "type":
        text = (step.get("action") or {}).get("type") == "rpa.type" and (step["action"].get("text") or "")
        if text:
            return jsonify(_post("/desktop/rpa/type", {"text": text})), 200
        return jsonify({"ok": True})
    # info
    return jsonify({"ok": True})

# ----- Igrovye prioritety -----

@bp.route("/game/priorities", methods=["GET"])
def game_pr_get():
    return jsonify({"ok": True, "items": pr_get()})

@bp.route("/game/priorities", methods=["POST"])
def game_pr_save():
    data = request.get_json(force=True, silent=True) or {}
    items = list(data.get("items") or [])
    pr_save(items)
    return jsonify({"ok": True, "count": len(items)})

@bp.route("/game/focus", methods=["POST"])
def game_pr_focus():
    return jsonify(pr_pick())

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_mentor.html")

def register(app):
    app.register_blueprint(bp)