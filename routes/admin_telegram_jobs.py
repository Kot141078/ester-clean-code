# -*- coding: utf-8 -*-
"""
routes/admin_telegram_jobs.py - panel: otpravka job-zaprosov cherez Telegram i prosmotr otvetov.

Marshruty:
  • GET  /admin/telegram_jobs
  • POST /admin/telegram_jobs/send     - {type, args, chat_id?, expect?}
  • GET  /admin/telegram_jobs/inbox    - spisok sokhranennykh otvetov (uid, summary, fayly)

Zemnoy abzats:
Eto «pult porucheniy»: odnoy knopkoy otpravlyaem udalennyy build_ticket / proj_build_publish i vidim, chto vernulos.

Mosty: yavnyy - UX nad jobs_rpc; skrytye - dry-rezhim, chistye JSON-otvety.

# c=a+b
"""
from __future__ import annotations
import os, json
from flask import Blueprint, jsonify, render_template, request

from modules.telegram.settings import load_settings  # type: ignore
from modules.telegram.jobs_rpc import send_job_request, list_job_replies  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_tgj = Blueprint("admin_telegram_jobs", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_tgj.get("/admin/telegram_jobs")
def page():
    return render_template("admin_telegram_jobs.html", ab=AB)

@bp_tgj.post("/admin/telegram_jobs/send")
def send():
    body = request.get_json(silent=True) or {}
    jtype = (body.get("type") or "").strip()
    jargs = body.get("args") or {}
    expect = (body.get("expect") or "json").strip()
    chat = body.get("chat_id")
    cfg = load_settings()
    tok = cfg.get("token")
    if not tok:
        return jsonify({"ok": False, "error": "no-token"}), 400
    if not chat:
        chat = (cfg.get("chats") or {}).get("last_chat")
    if not chat:
        return jsonify({"ok": False, "error": "no-chat"}), 400
    res = send_job_request(tok, int(chat), jtype, jargs, expect=expect)
    return jsonify(res)

@bp_tgj.get("/admin/telegram_jobs/inbox")
def inbox():
    return jsonify(list_job_replies())

def register_admin_telegram_jobs(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_tgj)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_telegram_jobs_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/telegram_jobs")
        def _p(): return page()

        @pref.post("/admin/telegram_jobs/send")
        def _s(): return send()

        @pref.get("/admin/telegram_jobs/inbox")
        def _i(): return inbox()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_tgj)
    return app