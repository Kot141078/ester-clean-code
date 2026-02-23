# -*- coding: utf-8 -*-
"""
routes/proactive_dispatch_routes.py - edinyy shlyuz proaktivnosti Ester → messendzhery.

MOSTY:
- (Yavnyy) /proactive/dispatch prinimaet semantiku (audience/intent/content) i kanal (whatsapp|telegram) i vyzyvaet /wa/send ili /tg/send.
- (Skrytyy #1) Deklarativnye pravila iz YAML (config/messaging_rules.yaml) - komu i kakim kanalom otpravlyat po tipu sobytiya.
- (Skrytyy #2) Idempotency po source_id, chtoby ne zadvoit rassylku pri povtorakh triggerov.

ZEMNOY ABZATs:
Pozvolyaet «usilit do maksimuma» proaktivnost, ne vmeshivayas v starye mekhanizmy - Ester generiruet sobytie, etot most beret na sebya marshrutizatsiyu.

# c=a+b
"""
from __future__ import annotations
import os, time, json, threading
from typing import Any, Dict, Optional, Tuple
from flask import Blueprint, request, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml
except Exception:
    yaml = None  # na dev perezhivem, budet tolko direct-mode

bp = Blueprint("proactive_dispatch_routes", __name__)

PROACTIVE_RULES_PATH = os.environ.get("PROACTIVE_RULES_PATH", "config/messaging_rules.yaml")

# Primitivnaya anti-dubl pamyat (in-memory)
_idem_lock = threading.Lock()
_idem_cache: dict[str, float] = {}

def _idem_mark(key: str, ttl: float = 300.0) -> bool:
    now = time.time()
    with _idem_lock:
        t = _idem_cache.get(key)
        if t and (now - t) < ttl:
            return False
        _idem_cache[key] = now
    return True

def _load_rules() -> Dict[str, Any]:
    if not yaml:
        return {}
    path = PROACTIVE_RULES_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        current_app.logger.warning("[PROACTIVE] rules load error: %s", e)
        return {}

@bp.route("/proactive/dispatch", methods=["POST"])
def proactive_dispatch():
    """
    body:
    {
      "channel": "whatsapp"|"telegram"|null,
      "to": "1555..."|777|null,
      "audience": "lawyer|student|friend|business|neutral",
      "intent": "letter|update|reminder|apology|request",
      "content": "tekst",
      "source": "ester:will:ruleX",   # chelovekochitaemyy istochnik
      "source_id": "uuid"             # dlya idempotentnosti
    }
    """
    j = request.get_json(force=True, silent=True) or {}

    source_id = (j.get("source_id") or "").strip()
    if source_id and not _idem_mark(source_id):
        return jsonify({"ok": True, "duplicate": True}), 200

    channel = (j.get("channel") or "").lower().strip() or None
    to = j.get("to")
    audience = (j.get("audience") or "neutral").strip().lower()
    intent = (j.get("intent") or "update").strip().lower()
    content = (j.get("content") or "").strip()

    rules = _load_rules()
    # 1) Esli net channel/to - podbiraem po pravilam
    if not (channel and to):
        key = f"{audience}:{intent}"
        rmap = rules.get("routes", {}).get(key) or rules.get("routes", {}).get(audience) or {}
        channel = channel or rmap.get("channel") or "whatsapp"
        to = to or rmap.get("to")

    if not (channel and to):
        return jsonify({"ok": False, "error": "routing_not_resolved"}), 400

    # 2) Delegiruem v konkretnyy kanal (lokalnyy HTTP-vyzov - bez vneshki)
    import urllib.request, json as _json
    if channel == "whatsapp":
        url = f"http://127.0.0.1:8080/wa/send?dry_run=1"  # dry po umolchaniyu bezopasen; s klyuchami uydet naruzhu
        body = {"to": to, "audience": audience, "intent": intent, "content": content}
    elif channel == "telegram":
        url = f"http://127.0.0.1:8080/tg/send?dry_run=1"
        body = {"chat_id": to, "audience": audience, "intent": intent, "content": content}
    else:
        return jsonify({"ok": False, "error": "unknown_channel"}), 400

    try:
        data = _json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            payload = resp.read().decode("utf-8", "ignore")
        return jsonify({"ok": True, "channel": channel, "to": to, "result": payload}), 200
    except Exception as e:
        current_app.logger.warning("[PROACTIVE] dispatch error: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "dispatch_failed"}), 502

def register(app):
    app.register_blueprint(bp)
    return bp