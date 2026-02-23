# -*- coding: utf-8 -*-
"""
routes/whatsapp_feed_routes.py - HTML-lenta dialogov WhatsApp.

MOSTY:
- (Yavnyy) GET /feeds/whatsapp - chitaet data/messaging/whatsapp.jsonl i pokazyvaet lentu.
- (Skrytyy #1) Bezopasno rabotaet, dazhe esli fayla poka net.
- (Skrytyy #2) Format zapisey - best-effort: {ts, from, to, text, direction}.

ZEMNOY ABZATs:
Panel nablyudeniya: skvoznaya lenta obscheniya «kto ↔ chto», kak v chate.

# c=a+b
"""
from __future__ import annotations
import os, json
from flask import Blueprint, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("whatsapp_feed_routes", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.get("/feeds/whatsapp")
def feed():
    path = os.getenv("WA_FEED_PATH", "data/messaging/whatsapp.jsonl")
    items = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    items.append(json.loads(line))
                except Exception:
                    continue
    items = items[-500:]
    return render_template("feed_whatsapp.html", items=items, title="Lenta WhatsApp")
# c=a+b