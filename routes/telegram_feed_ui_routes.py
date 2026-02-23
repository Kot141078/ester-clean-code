# -*- coding: utf-8 -*-
"""
routes/telegram_feed_ui_routes.py — veb-lenta obscheniya v Telegram + JSON-ruchki.

Puti:
  • GET  /chat/telegram                 — HTML-lenta (templates/telegram_feed.html)
  • GET  /chat/telegram/chats           — spisok chatov (aggregatsiya po feed.jsonl)
  • GET  /chat/telegram/events          — sobytiya chata (?chat_id=...&limit=500)

Sovmestimost:
  • Ispolzuet modules.telegram_feed_store.{latest,list_events}.
  • Glya otpravki soobscheniy UI dergaet POST /tg/send (sm. routes/telegram_send_routes.py).
  • Nichego ne menyaet v pamyati/protsessakh myshleniya — tolko chtenie/vizualizatsiya lenty.

# c=a+b
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules import telegram_feed_store as feed  # type: ignore
except Exception:
    feed = None  # type: ignore

bp = Blueprint("telegram_feed_ui", __name__, url_prefix="/chat/telegram")

@bp.get("/")
def telegram_feed_page():
    return render_template("telegram_feed.html")

@bp.get("/chats")
def telegram_chats():
    """
    Bozvraschaet agregirovannyy spisok chatov po lente:
    [{"chat_id":"...","chat_title":"...","last_ts":..., "last_text":"..."}]
    """
    if feed is None:
        return jsonify({"ok": False, "error": "feed_unavailable"}), 503

    # Berem dostatochno bolshoy khvost Re gruppiruem po chat_id
    items = feed.latest(limit=2000, chat_id=None)  # type: ignore[attr-defined]
    agg: Dict[str, Dict[str, Any]] = {}
    for ev in items:
        cid = str(ev.get("chat_id") or "")
        if not cid:
            continue
        rec = agg.get(cid)
        ts = float(ev.get("ts") or 0.0)
        title = ev.get("chat_title") or cid
        if rec is None or ts > float(rec.get("last_ts") or 0.0):
            agg[cid] = {
                "chat_id": cid,
                "chat_title": title,
                "last_ts": ts,
                "last_text": str(ev.get("text") or ""),
            }

    # R' vide massiva, uporyadochennogo po ubyvaniyu vremeni
    arr = sorted(agg.values(), key=lambda r: float(r.get("last_ts") or 0.0), reverse=True)
    return jsonify({"ok": True, "chats": arr})

@bp.get("/events")
def telegram_events():
    """
    Parametry:
      chat_id — obyazatelnyy identifikator chata
      limit   — maksimum sobytiy (po umolchaniyu 500)
    """
    if feed is None:
        return jsonify({"ok": False, "error": "feed_unavailable"}), 503

    chat_id = request.args.get("chat_id", "").strip()
    if not chat_id:
        return jsonify({"ok": False, "error": "chat_id required"}), 400
    limit = int(request.args.get("limit", "500"))
    limit = max(1, min(limit, 2000))

    events = feed.list_events(since=0.0, limit=limit, chat_id=str(chat_id), kind=None)  # type: ignore[attr-defined]
# return jsonify({"ok": True, "events": events})



def register(app):
    app.register_blueprint(bp)
    return app