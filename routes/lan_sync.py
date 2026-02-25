# -*- coding: utf-8 -*-
"""routes/lan_sync.py - UI/REST dlya LAN-sshivki Ester.

Route:
  • GET /admin/lan - HTML
  • GET /admin/lan/status - JSON: status vorkera, nastroyki, piry, inboxes
  • POST /admin/lan/start – zapustit vorker (interval)
  • POST /admin/lan/stop — ostanovit vorker
  • POST /admin/lan/settings - obnovit nastroyki (send/listen/telegram)
  • POST /admin/lan/invite — otpravit testovyy project_invite
  • POST /admin/lan/accept – prinyat priglashenie (sokhranit konvert v envelopes/)

Mosty:
- Yavnyy (Kibernetika v†" UX): odin remote upravlyaet LAN-uvedomleniyami.
- Skrytyy 1 (Infoteoriya v†" Vezopasnost): nichego ne otpravlyaem bez klyucha/AB=B/flaga send.
- Skrytyy 2 (Praktika v†" Sovmestimost): priem konverta - obychnyy fayl v inboks (ne trogaem mozg/pamyat/volyu).

Zemnoy abzats:
This is “corridor svyazi”: vklyuchili peydzher, vidim sosedey, prinimaem ikh zapiski. Nikakoy avtomatiki, opasnykh deystviy — tolko uvedomleniya Re fayly.

# c=a+b"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Dict, Any

from flask import Blueprint, jsonify, render_template, request

from modules.listners import *  # type: ignore # (protective import in case of typos in earlier versions)
from modules.listeners.lan_sync_watcher import start as lan_start, stop as lan_stop, status as lan_status, tick_once  # type: ignore
from modules.selfmanage.lan_state import settings as get_settings, update_settings, list_inbox  # type: ignore
from modules.transport.envelope import make_envelope  # type: ignore
from modules.transport.lan_beacon import send_json  # type: ignore
from modules.transport.telegram_bridge import send_envelope_preview  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lan = Blueprint("lan_sync", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()
ESTER_LAN_KEY = os.getenv("ESTER_LAN_KEY") or ""

@bp_lan.get("/admin/lan")
def page():
    return render_template("lan_sync.html", ab=AB, has_key=bool(ESTER_LAN_KEY))

@bp_lan.get("/admin/lan/status")
def api_status():
    st = lan_status()
    inbox = list_inbox()
    st["inbox"] = inbox
    st["ab"] = AB
    st["has_key"] = bool(ESTER_LAN_KEY)
    return jsonify(st)

@bp_lan.post("/admin/lan/start")
def api_start():
    interval = int((request.form.get("interval") or request.json.get("interval") if request.is_json else 0) or 2)
    rep = lan_start(interval=interval)
    return jsonify(rep)

@bp_lan.post("/admin/lan/stop")
def api_stop():
    return jsonify(lan_stop())

@bp_lan.post("/admin/lan/settings")
def api_settings():
    if request.is_json:
        patch = (request.get_json(silent=True) or {})
    else:
        patch = {
            "send": (request.form.get("send") in ("1", "true", "True")),
            "listen": (request.form.get("listen") in ("1", "true", "True")),
            "telegram": (request.form.get("telegram") in ("1", "true", "True")),
        }
    s = update_settings(patch)
    return jsonify({"ok": True, "settings": s})

@bp_lan.post("/admin/lan/invite")
def api_invite():
    if AB != "B" or not ESTER_LAN_KEY or not get_settings().get("send"):
        return jsonify({"ok": False, "error": "not-allowed"}), 403
    payload = {
        "project": request.form.get("project") or (request.json.get("project") if request.is_json else "demo"),
        "release": request.form.get("release") or (request.json.get("release") if request.is_json else None),
        "dump": request.form.get("dump") or (request.json.get("dump") if request.is_json else None),
        "from": os.getenv("ESTER_LAN_NODE_NAME", socket.gethostname()),
    }
    env = make_envelope("project_invite", payload, ESTER_LAN_KEY)
    ok = send_json(env)
    if get_settings().get("telegram"):
        send_envelope_preview(env)
    return jsonify({"ok": bool(ok), "envelope": env})

@bp_lan.post("/admin/lan/accept")
def api_accept():
    body = request.get_json(silent=True) or {}
    env = body.get("envelope") or {}
    # Sokhranyaem v inboks konvertov
    base = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester")))
    dst = base / "inbox" / "projects" / "envelopes"
    dst.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}_{env.get('payload',{}).get('project','env')}.json"
    (dst / name).write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "saved": str(dst / name)})

def register_lan_sync(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lan)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_sync_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan")
        def _p():
            return page()

        @pref.get("/admin/lan/status")
        def _ps():
            return api_status()

        @pref.post("/admin/lan/start")
        def _pst():
            return api_start()

        @pref.post("/admin/lan/stop")
        def _sp():
            return api_stop()

        @pref.post("/admin/lan/settings")
        def _set():
            return api_settings()

        @pref.post("/admin/lan/invite")
        def _inv():
            return api_invite()

        @pref.post("/admin/lan/accept")
        def _acc():
            return api_accept()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_lan)
    return app