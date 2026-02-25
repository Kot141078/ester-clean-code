# -*- coding: utf-8 -*-
"""routes/proactive_will_hook_routes.py - hook shlyuz dlya “voli” Ester: sobytie → auditoriya/namerenie → otpravka.

MOSTY:
- (Yavnyy) /proactive/hook/will prinimaet sobytie will/rrule/decision i proksiruet v /proactive/dispatch.
- (Skrytyy #1) Zagruzka deklarativnoy karty sobytiy (WILL_MAP_PATH) + fallback na PROACTIVE_RULES_PATH.
- (Skrytyy #2) Idempotentnost po source_id s TTL, chtoby ne produblirovat rassylki.

ZEMNOY ABZATs:
Pozvolyaet podklyuchit uzhe suschestvuyuschuyu “volyu” bez pravok: prosto shlite sobytiya syuda - marshrutizatsiya proizoydet korrektno i “po-chelovecheski”.

# c=a+b"""
from __future__ import annotations
import os, time, json, threading
from typing import Any, Dict, Optional
from flask import Blueprint, request, jsonify, current_app
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    import yaml
except Exception:
    yaml = None

bp = Blueprint("proactive_will_hook_routes", __name__)

WILL_MAP_PATH = os.environ.get("WILL_MAP_PATH", "config/will_messaging_map.yaml")
PROACTIVE_RULES_PATH = os.environ.get("PROACTIVE_RULES_PATH", "config/messaging_rules.yaml")

_idem_lock = threading.Lock()
_idem: dict[str, float] = {}

def _idem_ok(key: str, ttl: float = 300.0) -> bool:
    now = time.time()
    with _idem_lock:
        t = _idem.get(key)
        if t and (now - t) < ttl:
            return False
        _idem[key] = now
        return True

def _load_yaml(path: str) -> Dict[str, Any]:
    if not yaml or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        current_app.logger.warning("[WILL] load error %s: %s", path, e)
        return {}

def _resolve_route(ev: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """Vozvraschaet {audience,intent,channel?,to?}."""
    will = _load_yaml(WILL_MAP_PATH).get("map", {})
    if ev in will:
        cfg = dict(will[ev] or {})
        # We substitute the values ​​from the fascia (for example, then, referent, etc.)
        for k, v in list(cfg.items()):
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                key = v[2:-1]
                cfg[k] = facts.get(key)
        return cfg

    # Folbek: tolko audience/intent → dalshe /proactive/dispatch sam podberet channel/to iz PROACTIVE_RULES_PATH
    rules = _load_yaml(PROACTIVE_RULES_PATH)
    defaults = rules.get("defaults", {})
    return {"audience": defaults.get("audience", "neutral"), "intent": defaults.get("intent", "update")}

@bp.route("/proactive/hook/will", methods=["POST"])
def will_hook():
    """body:
    {
      "event": "bank.statement_check_due",
      "facts": {...}, # lyubye proizvolnye fakty
      "content": "optsionalno tekst", # esli pusto - soberem iz facts v /presets (sverkhu urovnya)
      "source_id": "uuid-like" # dlya idempotentnosti
    }"""
    j = request.get_json(force=True, silent=True) or {}
    source_id = (j.get("source_id") or "").strip()
    if source_id and not _idem_ok(source_id):
        return jsonify({"ok": True, "duplicate": True}), 200

    ev = (j.get("event") or "").strip()
    facts: Dict[str, Any] = j.get("facts") or {}
    content = (j.get("content") or "").strip()

    if not ev:
        return jsonify({"ok": False, "error": "event_required"}), 400

    cfg = _resolve_route(ev, facts)
    audience = (cfg.get("audience") or "neutral").strip()
    intent = (cfg.get("intent") or "update").strip()
    channel = (cfg.get("channel") or "").strip() or None
    to = cfg.get("to")

    # If the content is not specified, we will try to assemble it through presets, if a preset is specified inside the villa_map
    preset_key = (cfg.get("preset") or "").strip()
    if not content and preset_key:
        try:
            from modules.presets.letter_templates import PRESETS
            if preset_key in PRESETS:
                content = PRESETS[preset_key](facts)
        except Exception as e:
            current_app.logger.info("[WILL] preset error: %s", e)

    # Delegiruem v lokalnyy /proactive/dispatch
    import urllib.request, json as _json
    body = {
        "channel": channel,
        "to": to,
        "audience": audience,
        "intent": intent,
        "content": content or "",
        "source": f"will:{ev}",
        "source_id": source_id or f"will:{ev}:{int(time.time())}"
    }
    try:
        data = _json.dumps(body).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8080/proactive/dispatch", data=data,
                                     headers={"Content-Type":"application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            payload = resp.read().decode("utf-8", "ignore")
        return jsonify({"ok": True, "delegated": True, "result": payload}), 200
    except Exception as e:
        current_app.logger.warning("[WILL] dispatch error: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "dispatch_failed"}), 502


def register(app):
    app.register_blueprint(bp)
    return bp