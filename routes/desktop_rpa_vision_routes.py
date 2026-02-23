# -*- coding: utf-8 -*-
"""
routes/desktop_rpa_vision_routes.py - poisk shablonov po skrinshotu i klik v naydennyy boks.

Ruchki:
  POST /desktop/rpa/find_template {"template_b64":"...", "threshold":0.78}
  POST /desktop/rpa/click_template {"template_b64":"...", "threshold":0.78}

Realizatsiya:
- Berem tekuschiy /desktop/rpa/screen → png_b64
- Propuskaem cherez modules.vision.template_match
- Dlya click_template → /desktop/rpa/click po tsentru boksa

MOSTY:
- Yavnyy: (Obraz ↔ Klik) «nashel - nazhal».
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) oflayn-sovpadenie umenshaet setevye riski.
- Skrytyy #2: (Kibernetika ↔ Volya) formalizovannyy sensor vstraivaetsya v stsenarii/makrosy.

ZEMNOY ABZATs:
Ne trebuet izmeneniya agentov Windows/Linux - vsya «optika» na servere Ester.
Esli nuzhno bystree - mozhno pozzhe vynesti v agenta.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
import http.client, json

from modules.vision.template_match import find as tmpl_find
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("desktop_rpa_vision", __name__, url_prefix="/desktop/rpa")

def _get(path: str) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("GET", path)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        return json.loads(data)
    except Exception:
        return {"ok": False, "error": "bad_reply", "raw": data}

def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=3.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "ignore")
    conn.close()
    try:
        return json.loads(data)
    except Exception:
        return {"ok": False, "error": "bad_reply", "raw": data}

@bp.route("/find_template", methods=["POST"])
def find_template():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    tb64 = (data.get("template_b64") or "").strip()
    thr = float(data.get("threshold") or 0.78)
    if not tb64:
        return jsonify({"ok": False, "error": "template_b64_required"}), 400
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"):
        return jsonify({"ok": False, "error": "screen_failed"}), 500
    res = tmpl_find(scr["png_b64"], tb64, thr)
    return jsonify(res), (200 if res.get("ok") else 404)

@bp.route("/click_template", methods=["POST"])
def click_template():
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    tb64 = (data.get("template_b64") or "").strip()
    thr = float(data.get("threshold") or 0.78)
    if not tb64:
        return jsonify({"ok": False, "error": "template_b64_required"}), 400
    scr = _get("/desktop/rpa/screen")
    if not scr.get("ok"):
        return jsonify({"ok": False, "error": "screen_failed"}), 500
    res = tmpl_find(scr["png_b64"], tb64, thr)
    if not res.get("ok"):
        return jsonify(res), 404
    cx, cy = res["center"]["x"], res["center"]["y"]
    click = _post("/desktop/rpa/click", {"x": cx, "y": cy})
    return jsonify({"ok": True, "match": res, "click": click})


def register(app):
    app.register_blueprint(bp)
    return app