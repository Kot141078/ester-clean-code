# -*- coding: utf-8 -*-
"""
routes/chaos_routes.py - prostye khaos-inektsii (disabled by default): tempfile, cleanup, sleep.

Mosty:
- Yavnyy: (Nadezhnost ↔ Test) sozdaem kontroliruemye sboi (disk/zaderzhka).
- Skrytyy #1: (Kibernetika ↔ Kontrol) A/B=B po umolchaniyu - vyklyucheno.
- Skrytyy #2: (Nablyudaemost ↔ Ruchka) otsenit reaktsii guard'ov i degradatsiy.

Zemnoy abzats:
Eto «uchebnaya trevoga»: potrenirovalis - uvideli, gde khrustit, pochinili do nastoyaschey bedy.

# c=a+b
"""
from __future__ import annotations
import os, time
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_chaos = Blueprint("chaos", __name__)
CHAOS_AB = (os.getenv("CHAOS_AB","B") or "B").upper()
CHAOS_DIR = "data/chaos"

def register(app):
    app.register_blueprint(bp_chaos)

def _guard():
    return CHAOS_AB == "A"

@bp_chaos.route("/resilience/chaos/tempfile", methods=["POST"])
def chaos_tempfile():
    if not _guard():
        return jsonify({"ok": False, "error":"CHAOS_AB!=A"})
    d = request.get_json(True, True) or {}
    mb = max(1, int(d.get("size_mb", 100)))
    os.makedirs(CHAOS_DIR, exist_ok=True)
    p = os.path.join(CHAOS_DIR, f"blk_{int(time.time())}.bin")
    with open(p,"wb") as f:
        f.seek(mb*1024*1024 - 1)
        f.write(b"\0")
    return jsonify({"ok": True, "path": p, "size_mb": mb})

@bp_chaos.route("/resilience/chaos/cleanup", methods=["POST"])
def chaos_cleanup():
    if not _guard():
        return jsonify({"ok": False, "error":"CHAOS_AB!=A"})
    import shutil
    if os.path.isdir(CHAOS_DIR):
        shutil.rmtree(CHAOS_DIR, ignore_errors=True)
    return jsonify({"ok": True})

@bp_chaos.route("/resilience/chaos/sleep", methods=["POST"])
def chaos_sleep():
    if not _guard():
        return jsonify({"ok": False, "error":"CHAOS_AB!=A"})
    d = request.get_json(True, True) or {}
    sec = max(1, min(60, int(d.get("sec", 5))))
    time.sleep(sec)
    return jsonify({"ok": True, "slept": sec})
# c=a+b