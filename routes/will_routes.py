# -*- coding: utf-8 -*-
"""routes/will_routes.py - “volya/namereniya” Ester.

MOSTY:
- (Yavnyy) GET /will/status; POST /will/set; POST /will/append - khranenie stsenariev v data/will/will.json.
- (Skrytyy #1) Format sovmestim s buduschimi avtozapuskami (id,type,args,cron?).
- (Skrytyy #2) Bez fonovogo ispolneniya - tolko khranenie i prosmotr.

ZEMNOY ABZATs:
Kak "bloknot namereniy": zafiksirovat, what i kak delat pri starte/po zaprosu.

# c=a+b"""
from __future__ import annotations
import os, json, time, uuid
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("will_routes", __name__, url_prefix="/will")

def register(app):
    app.register_blueprint(bp)

BASE = "data/will"
PATH = os.path.join(BASE, "will.json")
os.makedirs(BASE, exist_ok=True)

def _read() -> Dict[str, Any]:
    if not os.path.isfile(PATH):
        return {"ts": int(time.time()), "intents": []}
    with open(PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _write(obj: Dict[str, Any]):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

@bp.get("/status")
def status():
    data = _read()
    return jsonify({"ok": True, "count": len(data.get("intents", [])), "file": PATH, "data": data})

@bp.post("/set")
def set_all():
    body = request.get_json(silent=True) or {}
    intents = body.get("intents")
    if not isinstance(intents, list):
        return jsonify({"ok": False, "error": "intents:list required"}), 400
    obj = {"ts": int(time.time()), "intents": intents}
    _write(obj)
    return jsonify({"ok": True, "saved": len(intents)})

@bp.post("/append")
def append():
    body = request.get_json(silent=True) or {}
    it = body.get("intent") or {}
    it.setdefault("id", str(uuid.uuid4()))
    it.setdefault("ts", int(time.time()))
    data = _read()
    arr = data.get("intents", [])
    arr.append(it)
    data["intents"] = arr
    _write(data)
    return jsonify({"ok": True, "intent": it})
# c=a+b