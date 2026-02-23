# -*- coding: utf-8 -*-
"""
routes/admin_telegram.py - panel Telegram fallback: nastroyki, status, otpravka.

Marshruty:
  • GET  /admin/telegram                 - HTML
  • GET  /admin/telegram/status          - token(maska), chat, kursor, inbox-svodka
  • POST /admin/telegram/config          - {token?, chat_id?}
  • POST /admin/telegram/ping            - testovyy ping→pong
  • POST /admin/telegram/send            - {path, kind, chat_id?} - otpravka fayla (s chankami)
  • GET  /admin/telegram/inbox           - svodka vkhodyaschikh

Zemnoy abzats:
Eto «pult telegrafa»: propisal token/chat, proveril svyaz, otpravil fayl. Dalshe uzly peretaskivayut gruzy i bez LAN.

Mosty: yavnyy - UX nad API/bridge; skrytye - dry-rezhim i chistyy JSON.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request
from modules.telegram.settings import load_settings, save_settings, set_token, set_chat, mask_token  # type: ignore
from modules.telegram.api import tg_send_message  # type: ignore
from modules.telegram.bridge import send_file_chunked, list_inbox, last_ticket_path, last_package_path  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_tg = Blueprint("admin_telegram", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_tg.get("/admin/telegram")
def page():
    return render_template("admin_telegram.html", ab=AB)

@bp_tg.get("/admin/telegram/status")
def status():
    cfg = load_settings()
    tok_mask = mask_token(cfg.get("token"))
    inbox = list_inbox()
    return jsonify({"ok": True, "ab": AB, "token_mask": tok_mask, "chats": cfg.get("chats",{}), "cursor": cfg.get("cursor",{}), "inbox": inbox})

@bp_tg.post("/admin/telegram/config")
def config():
    body = request.get_json(silent=True) or {}
    tok = (body.get("token") or "").strip()
    chat = body.get("chat_id")
    res = {}
    if tok:
        res["token"] = set_token(tok)
    if chat is not None:
        res["chat"] = set_chat(int(chat))
    return jsonify({"ok": True, "res": res})

@bp_tg.post("/admin/telegram/ping")
def ping():
    cfg = load_settings()
    tok = cfg.get("token")
    chat = (cfg.get("chats") or {}).get("last_chat")
    if not tok or not chat:
        return jsonify({"ok": False, "error": "token-or-chat-missing"}), 400
    res = tg_send_message(tok, int(chat), "ping")
    return jsonify({"ok": True, "send": res})

@bp_tg.post("/admin/telegram/send")
def send():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()
    kind = (body.get("kind") or "package").strip()
    chat = body.get("chat_id")
    cfg = load_settings()
    tok = cfg.get("token")
    if not tok:
        return jsonify({"ok": False, "error": "no-token"}), 400
    if not chat:
        chat = (cfg.get("chats") or {}).get("last_chat")
    if not chat:
        return jsonify({"ok": False, "error": "no-chat"}), 400
    res = send_file_chunked(tok, int(chat), path, kind=kind)
    return jsonify(res)

@bp_tg.get("/admin/telegram/inbox")
def inbox():
    return jsonify(list_inbox())

def register_admin_telegram(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_tg)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_telegram_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/telegram")
        def _p(): return page()

        @pref.get("/admin/telegram/status")
        def _s(): return status()

        @pref.post("/admin/telegram/config")
        def _c(): return config()

        @pref.post("/admin/telegram/ping")
        def _pp(): return ping()

        @pref.post("/admin/telegram/send")
        def _se(): return send()

        @pref.get("/admin/telegram/inbox")
        def _i(): return inbox()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_tg)
    return app