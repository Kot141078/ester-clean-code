# -*- coding: utf-8 -*-
"""
routes/missions_routes.py - zapusk i prokhozhdenie «uchebnykh missiy».

Ruchki:
  GET  /missions/list                  -> {ok, items:[{id,title,steps}]}
  GET  /missions/progress              -> {ok, done:{...}}
  POST /missions/start    {"id":"notepad_intro"} -> {ok, id, step:0}
  POST /missions/step     {"id":"notepad_intro","index":0} -> {ok, kind, payload}
  POST /missions/complete {"id":"notepad_intro"} -> {ok, done:true}

Otrisovka overleya:
- Na shage kind="overlay" berem tekuschiy /desktop/rpa/screen i risuem strelku/ramku (minimum).

Vypolnenie:
- kind="exec" zapuskaet workflow (cherez /rpa/workflows/run).

UI: /admin/missions - knopki i predprosmotr.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request, render_template
from typing import Any, Dict, List, Tuple
import http.client, json

from modules.thinking.missions import list_all, get, set_done, get_progress
from modules.vision.overlay import draw_arrow, draw_box_label
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("missions_routes", __name__, url_prefix="/missions")

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("GET", path)
    r = conn.getresponse()
    data = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(data)
    except Exception: return {"ok": False, "raw": data}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=30.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    data = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(data)
    except Exception: return {"ok": False, "raw": data}

@bp.route("/list", methods=["GET"])
def lst():
    return jsonify({"ok": True, "items": list_all()})

@bp.route("/progress", methods=["GET"])
def progress():
    return jsonify({"ok": True, **get_progress()})

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    mid = (data.get("id") or "").strip()
    m = get(mid)
    if not m:
        return jsonify({"ok": False, "error": "unknown_mission"}), 404
    return jsonify({"ok": True, "id": mid, "step": 0, "title": m["title"]})

@bp.route("/step", methods=["POST"])
def step():
    data = request.get_json(force=True, silent=True) or {}
    mid = (data.get("id") or "").strip()
    idx = int(data.get("index") or 0)
    m = get(mid)
    if not m:
        return jsonify({"ok": False, "error": "unknown_mission"}), 404
    if idx < 0 or idx >= len(m["steps"]):
        return jsonify({"ok": False, "error": "bad_index"}), 400
    st = m["steps"][idx]
    kind = st.get("kind")
    if kind == "overlay":
        scr = _get("/desktop/rpa/screen")
        if not scr.get("ok"): return jsonify({"ok": False, "error": "screen_failed"}), 500
        ov = None
        ovd = st.get("overlay") or {}
        if "arrow" in ovd:
            p1, p2 = ovd["arrow"]
            ov = draw_arrow(scr["png_b64"], (int(p1[0]),int(p1[1])), (int(p2[0]),int(p2[1])), st.get("label"))
        elif "box" in ovd:
            box = ovd["box"]
            ov = draw_box_label(scr["png_b64"], box, st.get("label") or "Shag")
        return jsonify({"ok": True, "kind": "overlay", "overlay_b64": ov, "index": idx})
    if kind == "exec":
        wf = st.get("workflow")
        res = _post("/rpa/workflows/run", {"name": wf})
        return jsonify({"ok": True, "kind": "exec", "workflow": wf, "result": res, "index": idx})
    if kind == "info":
        return jsonify({"ok": True, "kind": "info", "text": st.get("text",""), "index": idx})
    return jsonify({"ok": False, "error": "unknown_kind"}), 400

@bp.route("/complete", methods=["POST"])
def complete():
    data = request.get_json(force=True, silent=True) or {}
    mid = (data.get("id") or "").strip()
    set_done(mid)
    return jsonify({"ok": True, "done": True})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_missions.html")

def register(app):
    app.register_blueprint(bp)