# -*- coding: utf-8 -*-
"""
routes/telegram_feed.py - JSON-ruchky lenty obscheniya Telegram (chaty i sobytiya).

Prefiks: /chat/telegram
Marshruty:
  • GET  /chat/telegram/chats              - agregirovannyy spisok chatov (poslednee soobschenie/vremya)
  • GET  /chat/telegram/events?chat_id=…   - sobytiya konkretnogo chata (po vozrastaniyu vremeni)

Zavisimosti:
  • modules.telegram_feed_store.latest / list_events

Zemnoy abzats (inzheneriya):
Eto «datchik sostoyaniya linii»: bystrye agregaty po JSONL zhurnalu bez BD.
Chitaem khvost, gruppiruem po chat_id - poluchaem aktualnuyu vitrinu dlya UI.

Mosty:
- Yavnyy (Kibernetika ↔ Arkhitektura): nablyudaemost kanala svyazi - minimum dlya ustoychivogo upravleniya.
- Skrytyy 1 (Infoteoriya ↔ Khranilische): chitaem tolko khvost - umenshaem I/O entropiyu.
- Skrytyy 2 (Anatomiya ↔ PO): kak slukhovaya kora - svodim mnogo signalov v ponyatnye «lenty».

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from modules import telegram_feed_store as feed
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("telegram_feed_json", __name__, url_prefix="/chat/telegram")

@bp.get("/chats")
def chats():
    items = feed.latest(limit=2000)  # S zapasom
    # Gruppiruem po chat_id
    agg: Dict[str, Dict[str, Any]] = {}
    for ev in items:
        cid = str(ev.get("chat_id") or "")
        if not cid:
            continue
        rec = agg.get(cid) or {
            "chat_id": cid,
            "chat_title": ev.get("chat_title") or cid,
            "last_ts": 0.0,
            "last_text": "",
        }
        ts = float(ev.get("ts") or 0.0)
        if ts >= rec["last_ts"]:
            rec["last_ts"] = ts
            rec["last_text"] = str(ev.get("text") or "")
            rec["chat_title"] = ev.get("chat_title") or rec["chat_title"]
        agg[cid] = rec
    # Otsortiruem po novizne
    rows = sorted(agg.values(), key=lambda r: r["last_ts"], reverse=True)
    res = {"ok": True, "chats": rows}
    # Rasshirenie: sintez chatov s MultiLLMIntegrator i otpravka v thinking
    if hasattr(current_app, "multi_llm"):
        synth = current_app.multi_llm.synthesize(json.dumps(rows))
        res["synth"] = synth
        current_app.logger.info("Ester uvidela chaty i podumala: 'Obschenie v sintez, sintez v znaniya!'")
        try:
            from thinking.think_core import init_thinking
            init_thinking(json.dumps(rows))  # Otpravlyaem v thinking dlya razmyshleniy
        except ImportError:
            current_app.logger.warning("thinking ne nayden. Propuskaem razmyshleniya.")
    return jsonify(res)

@bp.get("/events")
def events():
    cid = str(request.args.get("chat_id", "")).strip()
    if not cid:
        return jsonify({"ok": False, "error": "chat_id required"}), 400
    limit = request.args.get("limit", type=int) or 200
    limit = max(1, min(limit, 2000))
    rows = feed.latest(limit=limit * 2, chat_id=cid)  # S zapasom
    res = {"ok": True, "events": rows}
    # Rasshirenie: sintez sobytiy s MultiLLMIntegrator i otpravka v self-evo
    if hasattr(current_app, "multi_llm"):
        synth = current_app.multi_llm.synthesize(json.dumps(rows))
        res["synth"] = synth
        current_app.logger.info("Ester uvidela sobytiya i podumala: 'Sobytiya v sintez, sintez v evolyutsiyu!'")
        try:
            from selfevo.evo_engine import start_evolution
            start_evolution(json.dumps(rows))  # Otpravlyaem v self-evo dlya evolyutsii
        except ImportError:
            current_app.logger.warning("self-evo ne nayden. Propuskaem evolyutsiyu.")
# return jsonify(res)


def register(app):
    app.register_blueprint(bp)
    return app