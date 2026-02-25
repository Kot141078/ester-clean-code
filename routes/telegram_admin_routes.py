# -*- coding: utf-8 -*-
# routes/telegram_admin_routes.py
"""routes/telegram_admin_routes.py - lokalnye admin-ruchki dlya inspektsii Telegram-dannykh.

Prefixes: /tg/admin
Marshruty (only local dostup: 127.0.0.1/::1/192.168.*):
  • GET /tg/admin/users - soderzhimoe tg_users.json
  • GET /tg/admin/state - telegram_state.json (last_update_id)
  • GET /tg/admin/chats — agregirovannyy spisok chatov (iz tg_feed.jsonl)
  • GET /tg/admin/tail?n=200 - khvost lenty (poslednie N sobytiy, po ubyvaniyu vremeni)

Zemnoy abzats (inzheneriya):
Eto servisnaya panel “na stanke”: posmotret, kto obschaetsya, kakoy progress po apdeytam, chto v posledney struzhke (khvost lenty).

Mosty:
- Yavnyy (Kibernetika v†" Arkhitektura): lokalnaya diagnostika - klyuch k ustoychivomu konturu webhook/polling.
- Skrytyy 1 (Infoteoriya v†" Khranilische): rabotaem s zhurnalami napryamuyu, bez VD - menshe tochek otkaza.
- Skrytyy 2 (Anatomiya v†" PO): kak perkussiya u vracha - prostye “prostukivaniya” dayut mnogo informatsii.

# c=a+b"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from flask import Blueprint, abort, jsonify, request

from modules import telegram_feed_store as feed
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_admin", __name__, url_prefix="/tg/admin")

DATA_DIR = (os.getenv("DATA_DIR") or os.getenv("PERSIST_DIR") or "./data").rstrip("/")
USERS_PATH = os.path.join(DATA_DIR, "tg_users.json")
STATE_PATH = os.path.join(DATA_DIR, "telegram_state.json")

def _local_only():
    remote = request.remote_addr or ""
    if remote not in {"127.0.0.1", "::1"} and not remote.startswith("192.168."):
        abort(403, description="local only")

@bp.get("/users")
def users():
    _local_only()
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            js = json.load(f)
    except FileNotFoundError:
        js = {}
    return jsonify({"ok": True, "users": js})

@bp.get("/state")
def state():
    _local_only()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            js = json.load(f)
    except FileNotFoundError:
        js = {"last_update_id": None}
    return jsonify({"ok": True, "state": js})

@bp.get("/chats")
def chats():
    _local_only()
    items = feed.latest(limit=5000)
    agg: Dict[str, Dict[str, Any]] = {}
    for ev in items:
        cid = str(ev.get("chat_id") or "")
        if not cid:
            continue
        rec = agg.get(cid) or {"chat_id": cid, "chat_title": ev.get("chat_title") or cid, "last_ts": 0.0, "last_text": ""}
        ts = float(ev.get("ts") or 0.0)
        if ts >= rec["last_ts"]:
            rec["last_ts"] = ts
            rec["last_text"] = str(ev.get("text") or "")
            rec["chat_title"] = ev.get("chat_title") or rec["chat_title"]
        agg[cid] = rec
    rows = sorted(agg.values(), key=lambda r: r["last_ts"], reverse=True)
    return jsonify({"ok": True, "chats": rows})

@bp.get("/tail")
def tail():
    _local_only()
    n = request.args.get("n", type=int) or 200
    n = max(1, min(n, 5000))
    rows = feed.latest(limit=n)
    # give in reverse order (we unwrap the fresh ones at the bottom for thailing)
    rows = list(reversed(rows))
    return jsonify({"ok": True, "events": rows})



def register(app):
    app.register_blueprint(bp)
    return app
