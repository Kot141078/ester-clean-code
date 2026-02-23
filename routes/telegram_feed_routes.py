# -*- coding: utf-8 -*-
"""
routes/telegram_feed_routes.py - HTML-lenta dialogov Telegram.

MOSTY:
- (Yavnyy) GET /feeds/telegram - chitaet data/messaging/telegram.jsonl i pokazyvaet «kto/chto/kogda».
- (Skrytyy #1) Esli fayl otsutstvuet - stranitsa pustaya, bez 500.
- (Skrytyy #2) Podkhvatyvaet zapisi, kotorye drugie moduli mogut pisat v JSONL (drop-in).

ZEMNOY ABZATs:
Okno nablyudeniya: vidno, kto napisal i chto otvetila Ester, bez vmeshatelstva v messendzher.

# c=a+b
"""
from __future__ import annotations
import os, json
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_feed_routes", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.get("/feeds/telegram")
def feed():
    path = os.getenv("TG_FEED_PATH", "data/messaging/telegram.jsonl")
    items = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
    items = items[-500:]
    return render_template("feed_telegram.html", items=items, title="Lenta Telegram")
# c=a+b