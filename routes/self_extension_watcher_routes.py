# -*- coding: utf-8 -*-
"""
routes/self_extension_watcher_routes.py - REST dlya nablyudatelya rasshireniy.

Endpointy:
  • GET  /self/extensions/watch/status
  • POST /self/extensions/watch/scan
  • POST /self/extensions/watch/approve
  • POST /self/extensions/watch/reject
  • POST /self/extensions/watch/pill
  • GET  /self/extensions/watch/chain

Mosty:
- Yavnyy: (Inzheneriya ↔ Volya) edinoe okno upravleniya priemkoy novykh sposobnostey.
- Skrytyy #1: (Bezopasnost ↔ Audit) karantin i tsepochka sobytiy dostupny cherez API.
- Skrytyy #2: (UX ↔ Podderzhka) «tabletka» daet operatoru myagkiy overrayd na ogranichennoe vremya.

Zemnoy abzats:
Eto kak prokhodnaya s okhranoy: proveryaem, vpuskaem po spisku, somnitelnykh - v storonku, vse zapisano.

# c=a+b
"""
from __future__ import annotations
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ext_watch = Blueprint("self_ext_watch", __name__)

try:
    from modules.self.extension_watcher import status as _status, scan as _scan, approve as _approve, reject as _reject, pill_arm as _pill_arm, pill_disarm as _pill_disarm, chain_tail as _chain  # type: ignore
except Exception:
    _status = _scan = _approve = _reject = _pill_arm = _pill_disarm = _chain = None  # type: ignore

def register(app):
    app.register_blueprint(bp_ext_watch)

@bp_ext_watch.route("/self/extensions/watch/status", methods=["GET"])
def api_status():
    if _status is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    return jsonify(_status())

@bp_ext_watch.route("/self/extensions/watch/scan", methods=["POST"])
def api_scan():
    if _scan is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    auto = bool(data.get("auto", False))
    return jsonify(_scan(auto=auto))

@bp_ext_watch.route("/self/extensions/watch/approve", methods=["POST"])
def api_approve():
    if _approve is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "")
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    return jsonify(_approve(name))

@bp_ext_watch.route("/self/extensions/watch/reject", methods=["POST"])
def api_reject():
    if _reject is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    name = str(data.get("name") or "")
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    return jsonify(_reject(name))

@bp_ext_watch.route("/self/extensions/watch/pill", methods=["POST"])
def api_pill():
    if _pill_arm is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    arm = bool(data.get("arm", True))
    if arm:
        ttl = int(data.get("ttl_sec", 300))
        return jsonify(_pill_arm(ttl))
    return jsonify(_pill_disarm())

@bp_ext_watch.route("/self/extensions/watch/chain", methods=["GET"])
def api_chain():
    if _chain is None:
        return jsonify({"ok": False, "error": "extension watcher unavailable"}), 500
    return jsonify(_chain())