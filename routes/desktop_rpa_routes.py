# -*- coding: utf-8 -*-
"""
routes/desktop_rpa_routes.py - REST-proksi k lokalnomu RPA-agentu Ester (127.0.0.1:8732).

MOSTY:
- Yavnyy: (Veb ↔ Deystviya) edinyy HTTP-proksi k RPA i OCR.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) whitelist putey.
- Skrytyy #2: (Kibernetika ↔ Volya) s UI i pravilami mysley razdelyayut odin transport.

ZEMNOY ABZATs:
Server Ester ne znaet detaley OS: on delegiruet v lokalnyy agent.
Dobavleny ekran/ocr/slot - dostatochno dlya bazovoy avtonomii bez oblakov.

# c=a+b
"""
from __future__ import annotations

import json
import http.client
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_rpa", __name__, url_prefix="/desktop/rpa")

_ALLOW_PATHS = {"/health", "/open", "/click", "/type", "/screen", "/ocr_click", "/slot"}
_AGENT_HOST = "127.0.0.1"
_AGENT_PORT = 8732

def _call_agent(path: str, method: str = "GET", payload: Dict[str, Any] | None = None):
    if path not in _ALLOW_PATHS:
        return {"ok": False, "error": "forbidden"}, 403
    try:
        conn = http.client.HTTPConnection(_AGENT_HOST, _AGENT_PORT, timeout=3.0)
        if method == "GET":
            conn.request("GET", path)
        else:
            body = json.dumps(payload or {})
            conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", "ignore")
        conn.close()
        try:
            obj = json.loads(data)
        except Exception:
            obj = {"ok": False, "error": "bad_agent_reply", "raw": data}
        return obj, resp.status
    except Exception as e:
        return {"ok": False, "error": f"agent_unreachable: {e}"}, 500

@bp.route("/health", methods=["GET"])
def rpa_health():
    obj, code = _call_agent("/health", "GET")
    return jsonify(obj), code

@bp.route("/screen", methods=["GET"])
def rpa_screen():
    obj, code = _call_agent("/screen", "GET")
    return jsonify(obj), code

@bp.route("/open", methods=["POST"])
def rpa_open():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    app = (data.get("app") or "").strip().lower()
    if app not in {"chrome", "notepad", "explorer", "cmd", "powershell", "xterm"}:
        return jsonify({"ok": False, "error": "app_not_allowed"}), 400
    obj, code = _call_agent("/open", "POST", {"app": app})
    return jsonify(obj), code

@bp.route("/click", methods=["POST"])
def rpa_click():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        x = int(data.get("x")); y = int(data.get("y"))
    except Exception:
        return jsonify({"ok": False, "error": "x_y_required"}), 400
    obj, code = _call_agent("/click", "POST", {"x": x, "y": y})
    return jsonify(obj), code

@bp.route("/type", methods=["POST"])
def rpa_type():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "")
    if not text:
        return jsonify({"ok": False, "error": "text_required"}), 400
    obj, code = _call_agent("/type", "POST", {"text": text})
    return jsonify(obj), code

@bp.route("/ocr_click", methods=["POST"])
def rpa_ocr_click():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    needle = (data.get("needle") or "").strip()
    lang = (data.get("lang") or "eng+rus").strip()
    if not needle:
        return jsonify({"ok": False, "error": "needle_required"}), 400
    obj, code = _call_agent("/ocr_click", "POST", {"needle": needle, "lang": lang})
    return jsonify(obj), code

@bp.route("/slot", methods=["POST"])
def rpa_slot():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    slot = (data.get("slot") or "").strip().upper()
    if slot not in {"A", "B"}:
        return jsonify({"ok": False, "error": "slot_invalid"}), 400
    obj, code = _call_agent("/slot", "POST", {"slot": slot})
    return jsonify(obj), code

def register(app):
    app.register_blueprint(bp)