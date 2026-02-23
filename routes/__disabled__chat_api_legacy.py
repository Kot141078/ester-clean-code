# -*- coding: utf-8 -*-
"""
routes/chat_api.py — «sovmestimyy» chat-router dlya Ester.

MOSTY:
- (Yavnyy) UI/bot ↔ /chat|/ester/chat/message (edinyy kontrakt {message, mode, use_rag, temperature}).
- (Skrytyy #1) judge/cloud/lmstudio ↔ OpenAI-sovmestimye endpointy (unifitsirovannyy vyzov).
- (Skrytyy #2) Avtologirovanie v ~/.ester/vstore/ester_chat_log.json dlya pamyati.

ZEMNOY ABZATs:
Kak elektrik s testerom: u nas odna «vilka» (klient), neskolko «rozetok» (provayderov).
Etot fayl — raspredelitelnaya korobka: prinimaet odin format i bezopasno podaet pitanie tuda,
kuda poprosili, ne dopuskaya «ne toy rozetki» i korotkogo zamykaniya.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from flask import Blueprint, request, jsonify
from pathlib import Path
from datetime import datetime
import json
import os
import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -------- Konfig provayderov (cherez ENV) --------
LMSTUDIO_BASE  = os.getenv("LMSTUDIO_BASE", "http://127.0.0.1:1234")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "qwen/qwen3-vl-8b")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "")  # obychno ne nuzhen

OPENAI_API_BASE  = os.getenv("OPENAI_API_BASE", "https://api.openai.com")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# judge mozhet byt otdelnym agregatorom; esli ne zadan — ispolzuem cloud-nastroyki
JUDGE_BASE     = os.getenv("JUDGE_BASE", OPENAI_API_BASE)
JUDGE_API_KEY  = os.getenv("JUDGE_API_KEY", OPENAI_API_KEY)
JUDGE_MODEL    = os.getenv("JUDGE_MODEL", os.getenv("OPENAI_JUDGE_MODEL", OPENAI_MODEL))

DEFAULT_MODE   = os.getenv("ESTER_DEFAULT_MODE", "lmstudio")

# -------- Vneshnie mosty (optsionalno) --------
try:
    from modules.net_bridge import search as net_search  # type: ignore
except Exception:
    net_search = None  # set neobyazatelna

# -------- Lokalnoe sostoyanie/log --------
STATE_DIR = Path(os.getenv("ESTER_STATE_DIR", str(Path.home() / ".ester"))).expanduser()
VSTORE_DIR = STATE_DIR / "vstore"
VSTORE_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOG_FILE = VSTORE_DIR / "ester_chat_log.json"

def _chat_log(entry: Dict[str, Any]) -> None:
    try:
        logs: List[Dict[str, Any]] = []
        if CHAT_LOG_FILE.exists():
            try:
                logs = json.loads(CHAT_LOG_FILE.read_text(encoding="utf-8"))
            except Exception:
                logs = []
        logs.append(entry)
        if len(logs) > 1000:
            logs = logs[-500:]
        CHAT_LOG_FILE.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # log — best effort
        pass

# -------- Unifitsirovannyy vyzov OpenAI-sovmestimykh API --------
def _call_openai_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 800,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    j = resp.json()
    content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {"ok": True, "answer": content, "raw": j}

# -------- Blueprint --------
bp = Blueprint("chat_api_legacy_compat", __name__)

def _extract_message(data: Dict[str, Any]) -> str:
    # podderzhivaem i "query" (staryy telegram-adapter), i "message"
    msg = data.get("message")
    if not msg:
        msg = data.get("query")
    return (msg or "").strip()

def _maybe_enrich_with_net(message: str, sid: Optional[str]) -> (str, bool, int):
    if not message or net_search is None:
        return message, False, 0
    detect = ["internet", "novosti", "tseny", "search", "posmotri", "aktualnye"]
    if any(w in message.lower() for w in detect):
        try:
            res = net_search(message, max_items=5)  # type: ignore
            ok = bool(res.get("ok"))
            items = res.get("items", []) if isinstance(res, dict) else []
            if ok and items:
                enriched = f"{message}\n\n[NET CLUES]\n" + json.dumps(items, ensure_ascii=False)
                _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "query": message, "net_items": len(items)})
                return enriched, True, len(items)
            else:
                _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "query": message, "net_fail": True})
        except Exception as e:
            _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "query": message, "net_error": str(e)})
    return message, False, 0

# Osnovnaya ruchka; delaem dva puti na odnu funktsiyu (sovmestimost frontov)
@bp.post("/chat/message")
@bp.post("/ester/chat/message")
def chat_message():
    data: Dict[str, Any] = request.json or {}
    mode = str(data.get("mode") or DEFAULT_MODE).lower()
    sid = data.get("sid")
    use_rag = bool(data.get("use_rag", True))
    temperature = float(data.get("temperature", 0.7))
    message = _extract_message(data)

    if not message:
        return jsonify({"ok": False, "error": "no_message"}), 400

    # enrich (optsionalno)
    msg_for_llm = message
    net_used = False
    net_count = 0
    if use_rag:
        msg_for_llm, net_used, net_count = _maybe_enrich_with_net(message, sid)

    messages = [{"role": "user", "content": msg_for_llm}]

    try:
        if mode == "lmstudio":
            # LM Studio obychno sovmestim s OpenAI API (bez klyucha)
            res = _call_openai_chat(
                base_url=LMSTUDIO_BASE,
                api_key=LMSTUDIO_API_KEY,
                model=LMSTUDIO_MODEL,
                messages=messages,
                temperature=temperature,
            )
            provider = "lmstudio"
            answer = res["answer"]

        elif mode == "cloud":
            if not OPENAI_API_KEY:
                return jsonify({"ok": False, "error": "cloud_api_key_missing"}), 500
            res = _call_openai_chat(
                base_url=OPENAI_API_BASE,
                api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
            )
            provider = "cloud"
            answer = res["answer"]

        elif mode == "judge":
            # judge — otdelnyy bazovyy URL/model (po umolchaniyu = cloud)
            if not JUDGE_API_KEY and "api.openai.com" in (JUDGE_BASE or ""):
                # esli judge zavyazan na OpenAI — klyuch obyazatelen
                return jsonify({"ok": False, "error": "judge_api_key_missing"}), 500
            res = _call_openai_chat(
                base_url=JUDGE_BASE,
                api_key=JUDGE_API_KEY,
                model=JUDGE_MODEL,
                messages=messages,
                temperature=temperature,
            )
            provider = "judge"
            answer = res["answer"]

        else:
            return jsonify({"ok": False, "error": "unsupported_mode", "mode": mode}), 400

    except requests.HTTPError as he:
        out = {"ok": False, "error": f"http_error: {he}", "mode": mode, "provider": mode}
        _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "response": out})
        return jsonify(out), 502
    except Exception as e:
        out = {"ok": False, "error": f"provider_error: {e}", "mode": mode, "provider": mode}
        _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "response": out})
        return jsonify(out), 500

    out = {
        "ok": True,
        "sid": sid,
        "mode": mode,
        "provider": provider,
        "answer": answer,
        "net_used": net_used,
        "net_items": net_count,
    }
    _chat_log({"ts": datetime.utcnow().isoformat(), "sid": sid, "response": out})
    return jsonify(out)

def register(app):
    """
    Gibkaya registratsiya:
    - Po umolchaniyu LEGASI-rout otklyuchen (ESTER_DISABLE_LEGACY_CHAT="1") — chtoby ne konfliktovat s novym chatom.
    - Postav ESTER_DISABLE_LEGACY_CHAT="0", esli khochesh yavno vklyuchit etu ruchku.
    """
    if os.getenv("ESTER_DISABLE_LEGACY_CHAT", "1") == "1":
        print("[chat_api legacy] disabled")
        return
    app.register_blueprint(bp)
    print("[chat_api legacy] enabled")