# -*- coding: utf-8 -*-
"""
routes/telegram_send_routes.py - unifitsirovannaya otpravka v Telegram.

MOSTY:
- (Yavnyy) /tg/send - obschiy kontrakt: libo raw text, libo semantic (audience/intent/content) cherez obschiy stilevoy dvizhok.
- (Skrytyy #1) A/B bezopasnyy katbek: bez tokena ili pri oshibke seti → dry echo.
- (Skrytyy #2) Edinoobrazie s WA: odinakovye polya zaprosa, chtoby proaktivnyy most rabotal simmetrichno.

ZEMNOY ABZATs:
Delaet Telegram ravnopravnym interfeysom naryadu s WA, bez lomki uzhe suschestvuyuschikh chastey.

# c=a+b
"""
from __future__ import annotations
import os
from typing import Any, Dict
from flask import Blueprint, request, jsonify, current_app
from modules.persona_style import render_message
from modules.thinking.action_registry import invoke_guarded
from modules.volition.volition_gate import VolitionContext, get_default_gate

bp = Blueprint("telegram_send_routes", __name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


@bp.route("/tg/send", methods=["POST"])
def tg_send():
    """
    body: { chat_id: int|str, text?: str, audience?: str, intent?: str, content?: str }
    query: dry_run=1 - forsirovat lokalnyy echo.
    """
    j = request.get_json(force=True, silent=True) or {}
    chat_id = j.get("chat_id")
    text = j.get("text")
    audience = j.get("audience")
    intent = j.get("intent")
    content = j.get("content")

    if not chat_id or (not text and not content):
        return jsonify({"ok": False, "error": "chat_id_or_text_missing"}), 400

    if not text:
        text = render_message(audience=audience or "neutral", intent=intent or "update", content=content or "")
    dry_from_query = request.args.get("dry_run")
    dry_from_body = j.get("dry_run")
    if dry_from_query is not None:
        dry_flag: Any = str(dry_from_query).strip().lower() in {"1", "true", "yes", "on", "y"}
    elif dry_from_body is not None:
        dry_flag = bool(dry_from_body)
    else:
        dry_flag = None  # default sender policy: dry-run in offline-first mode

    if not TELEGRAM_BOT_TOKEN:
        current_app.logger.info("TELEGRAM_BOT_TOKEN not set; sender will stay in safe deny/dry mode.")

    gate = get_default_gate()
    rep = invoke_guarded(
        "messages.telegram.send",
        {
            "text": text,
            "chat_id": str(chat_id),
            "window_id": str(j.get("window_id") or ""),
            "reason": str(j.get("reason") or "route:/tg/send"),
            "dry_run": dry_flag,
        },
        ctx=VolitionContext(
            chain_id=str(j.get("chain_id") or "http_tg_send"),
            step="action",
            actor="agent:telegram_send_route",
            intent="telegram_send_message",
            action_kind="messages.telegram.send",
            route=request.path or "/tg/send",
            needs=["network", "comm"],
            budgets=dict(j.get("budgets") or {}),
            metadata={"chat_id": str(chat_id)},
        ),
        gate=gate,
    )
    code = 200 if rep.get("ok") else 403
    return jsonify(rep), code

def register(app):
    app.register_blueprint(bp)
    return bp
