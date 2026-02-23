# -*- coding: utf-8 -*-
"""
routes/node_info.py — UI/REST: «Profile uzla».

Marshruty:
  • GET  /admin/node            — HTML-stranitsa «Profile uzla»
  • GET  /admin/node/status     — JSON-inventar
  • GET  /admin/node/export     — JSON-profile (skachat)
  • POST /admin/node/p2p-send   — polozhit profile v outbox Re popytatsya otpravit po P2P (Telegram)
  • POST /admin/node/usb-write  — zapisat profile na fleshku: ESTER/passport/node_<host>.json
  • GET  /admin/node/probe      — spisok tomov (dlya vybora fleshki)

Zemnoy abzats:
Odin ekran: posmotret «profile», otpravit ego «kurerom» (P2P) ili polozhit na fleshku.

Mosty:
- Yavnyy (Nablyudaemost v†" Orkestratsiya): profile kak edinyy artefakt sostoyaniya uzla.
- Skrytyy 1 (Infoteoriya v†" Prozrachnost): pryamoy JSON, bez magii.
- Skrytyy 2 (Praktika v†" Sovmestimost): tot zhe envelope Re ta zhe USB-struktura ESTER/.

# c=a+b
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

from modules.selfmanage.node_inventory import inventory, passport, write_passport  # type: ignore
from modules.transport.spool import put_outbox  # type: ignore
from modules.transport.telegram_driver import send_envelope  # type: ignore
from modules.transport.channel_routing import check_send_allowed  # type: ignore
from modules.transport.p2p_settings import load_settings  # type: ignore
from modules.usb.usb_probe import list_targets  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_node = Blueprint("node_info", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_node.get("/admin/node")
def page():
    return render_template("node_info.html", ab=AB)

@bp_node.get("/admin/node/status")
def api_status():
    try:
        inv = inventory()
        return jsonify({"ok": True, "ab": AB, "inventory": inv})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp_node.get("/admin/node/export")
def api_export():
    return jsonify({"ok": True, "ab": AB, "passport": passport()})

@bp_node.post("/admin/node/p2p-send")
def api_p2p_send():
    s = load_settings()
    if not (s.get("enable") and check_send_allowed(s)):
        return jsonify({"ok": False, "error": "p2p-disabled-or-not-allowed"}), 403
    env = {
        "type": "node_passport",
        "ts": passport()["ts"],
        "src": {"node": inventory().get("node")},
        "sig": "",
        "payload": passport(),
    }
    path = put_outbox(env)
    rep = send_envelope(env, s, ab_mode=AB)
    return jsonify({"ok": bool(rep.get("ok")), "path": path, "send": rep})

@bp_node.post("/admin/node/usb-write")
def api_usb_write():
    data = request.get_json(silent=True) or {}
    mount = data.get("mount") or ""
    node = inventory().get("node")
    out = Path(mount) / "ESTER" / "passport" / f"node_{node}.json"
    rep = write_passport(str(out), dry=(AB != "B"))
    return jsonify({"ok": rep.get("ok", False), "result": rep})

@bp_node.get("/admin/node/probe")
def api_probe():
    return jsonify({"ok": True, "targets": list_targets()})

def register_node_info(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_node)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("node_info_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/node")
        def _p(): return page()

        @pref.get("/admin/node/status")
        def _ps(): return api_status()

        @pref.get("/admin/node/export")
        def _pe(): return api_export()

        @pref.post("/admin/node/p2p-send")
        def _pp(): return api_p2p_send()

        @pref.post("/admin/node/usb-write")
        def _pu(): return api_usb_write()

        @pref.get("/admin/node/probe")
        def _pr(): return api_probe()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_node)
    return app