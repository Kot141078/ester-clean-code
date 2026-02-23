# -*- coding: utf-8 -*-
"""
routes/rpa_record_routes.py - proksi-ruchki dlya zapisi RPA-deystviy (REC→PLAY).

Ruchki:
  POST /rpa/record/start {"session":"s1"}
  POST /rpa/record/stop  {"session":"s1"}
  POST /rpa/record/export {"session":"s1","name":"wf_s1"}
  --- Proksi deystviya (pisat i ispolnyat srazu):
  POST /rpa/record/open   {"session":"s1","app":"notepad"}
  POST /rpa/record/click  {"session":"s1","x":100,"y":200}
  POST /rpa/record/type   {"session":"s1","text":"Hello"}
  POST /rpa/record/hotkey {"session":"s1","seq":"CTRL+S"}
  POST /rpa/record/ocr_click {"session":"s1","needle":"OK","lang":"eng+rus"}

Vnutri: vyzyvaet sootvetstvuyuschie /desktop/rpa/*, parallelno dobavlyaya sobytie v sessiyu.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
import http.client, json

from modules.thinking.recorder import start as rec_start, stop as rec_stop, append as rec_append, export_to_workflow
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("rpa_record_routes", __name__, url_prefix="/rpa/record")

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=4.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    data = r.read().decode("utf-8","ignore")
    conn.close()
    try: return json.loads(data)
    except Exception: return {"ok": False, "raw": data}

@bp.route("/start", methods=["POST"])
def start():
    sess = (request.get_json(force=True, silent=True) or {}).get("session","").strip()
    return jsonify(rec_start(sess)), 200

@bp.route("/stop", methods=["POST"])
def stop():
    sess = (request.get_json(force=True, silent=True) or {}).get("session","").strip()
    return jsonify(rec_stop(sess)), 200

@bp.route("/export", methods=["POST"])
def export():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    name = (data.get("name") or "").strip()
    return jsonify(export_to_workflow(sess, name)), 200

# --- Proksi deystviy ---
@bp.route("/open", methods=["POST"])
def p_open():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    app = (data.get("app") or "").strip()
    res = _post("/desktop/rpa/open", {"app": app})
    rec_append(sess, {"type":"open","app":app})
    return jsonify(res), (200 if res.get("ok") else 400)

@bp.route("/click", methods=["POST"])
def p_click():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    x, y = int(data.get("x",0)), int(data.get("y",0))
    res = _post("/desktop/rpa/click", {"x": x, "y": y})
    rec_append(sess, {"type":"click","x":x,"y":y})
    return jsonify(res), (200 if res.get("ok") else 400)

@bp.route("/type", methods=["POST"])
def p_type():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    text = (data.get("text") or "")
    res = _post("/desktop/rpa/type", {"text": text})
    rec_append(sess, {"type":"type","text":text})
    return jsonify(res), (200 if res.get("ok") else 400)

@bp.route("/hotkey", methods=["POST"])
def p_hotkey():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    seq = (data.get("seq") or "").strip()
    res = _post("/desktop/window/hotkey", {"seq": seq})
    rec_append(sess, {"type":"hotkey","seq":seq})
    return jsonify(res), (200 if res.get("ok") else 400)

@bp.route("/ocr_click", methods=["POST"])
def p_ocr_click():
    data = request.get_json(force=True, silent=True) or {}
    sess = (data.get("session") or "").strip()
    needle = (data.get("needle") or "").strip()
    lang = (data.get("lang") or "eng+rus")
    res = _post("/desktop/rpa/ocr_click", {"needle": needle, "lang": lang})
    rec_append(sess, {"type":"ocr_click","needle":needle,"lang":lang})
    return jsonify(res), (200 if res.get("ok") else 404)

def register(app):
    app.register_blueprint(bp)