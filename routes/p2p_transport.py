# -*- coding: utf-8 -*-
"""
routes/p2p_transport.py — UI/REST dlya P2P cherez Telegram.

Marshruty:
  • GET  /admin/p2p           — HTML
  • GET  /admin/p2p/status    — JSON: {settings, queues}
  • POST /admin/p2p/save      — sokhranit nastroyki
  • POST /admin/p2p/test-send — polozhit testovyy «konvert» v outbox Re popytatsya otpravit
  • POST /admin/p2p/poll      — opros vkhodyaschikh (odin tsikl)

Mosty:
- Yavnyy (Kibernetika v†" UX): «vklyuchi, sokhrani, test» — odnogo ekrana dostatochno.
- Skrytyy 1 (Infoteoriya v†" Prozrachnost): pokazyvaem razmery ocheredey Re rezhim AB.
- Skrytyy 2 (Praktika v†" Sovmestimost): test-konvert — eto pravilnyy envelope.

Zemnoy abzats:
Odin ekran — chtoby P2P zarabotal bez boli: vklyuchil, vvel token/chat, proveril «test-otpravkoy».

# c=a+b
"""
from __future__ import annotations

import os
import time
from flask import Blueprint, jsonify, render_template, request

from modules.transport.p2p_settings import load_settings, save_settings  # type: ignore
from modules.transport.spool import ensure_dirs, list_queue, put_outbox  # type: ignore
from modules.transport.telegram_driver import send_envelope, poll_updates  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_p2p = Blueprint("p2p_transport", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_p2p.get("/admin/p2p")
def page():
    return render_template("p2p_transport.html", ab=AB)

@bp_p2p.get("/admin/p2p/status")
def api_status():
    s = load_settings()
    dirs = ensure_dirs()
    q = {k: len(list_queue(k)) for k in ("outbox","inbox","pending","sent","failed")}
    return jsonify({"ok": True, "ab": AB, "settings": s, "queues": q, "dirs": dirs})

@bp_p2p.post("/admin/p2p/save")
def api_save():
    data = request.get_json(silent=True) or {}
    s = save_settings({
        "enable": bool(data.get("enable")),
        "tg_bot_token": data.get("tg_bot_token") or "",
        "tg_chat_id": data.get("tg_chat_id") or "",
        "shared_key": data.get("shared_key") or "",
        "poll_interval": data.get("poll_interval") or 10,
        "text_limit": data.get("text_limit") or 3500,
    })
    return jsonify({"ok": True, "settings": s})

@bp_p2p.post("/admin/p2p/test-send")
def api_test_send():
    s = load_settings()
    env = {
        "type": "p2p_test",
        "ts": int(time.time()),
        "src": {"node": "local"},
        "sig": "",
        "payload": {"note": "hello-from-p2p", "ab": AB},
    }
    path = put_outbox(env)
    rep = send_envelope(env, s, ab_mode=AB) if (s.get("enable") and s.get("tg_bot_token") and s.get("tg_chat_id")) else {"ok": False, "reason": "disabled-or-missing-settings"}
    return jsonify({"ok": rep.get("ok", False), "path": path, "send": rep})

@bp_p2p.post("/admin/p2p/poll")
def api_poll():
    s = load_settings()
    rep = poll_updates(s, ab_mode=AB)
    return jsonify({"ok": rep.get("ok", False), "received": len(rep.get("updates", [])), "dry": rep.get("dry", False)})

def register_p2p_transport(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_p2p)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("p2p_transport_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/p2p")
        def _p():
            return page()

        @pref.get("/admin/p2p/status")
        def _ps():
            return api_status()

        @pref.post("/admin/p2p/save")
        def _sv():
            return api_save()

        @pref.post("/admin/p2p/test-send")
        def _ts():
            return api_test_send()

        @pref.post("/admin/p2p/poll")
        def _pl():
            return api_poll()

# app.register_blueprint(pref)
# c=a+b



def register(app):
    app.register_blueprint(bp_p2p)
    return app