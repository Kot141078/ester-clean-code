
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.llm — shlyuz LLM c myagkim folbekom brokera.
Mosty:
- Yavnyy: pri importe dobavlyaem nedostayuschie funktsii v modules.llm.broker (chat/complete/embeddings/ping).
- Skrytyy #1: (DX ↔ Offlayn) — ispolzuem LM Studio cherez autoconfig_settings, esli osnovnoy broker molchit.
- Skrytyy #2: (A/B ↔ Otkat) — ENV `ESTER_LLM_FALLBACK` i `ESTER_LLM_AB`.

Zemnoy abzats:
Kod zovet `modules.llm.broker.chat(...)`, a broker mozhet byt «tonkim» ili slomannym. My myagko podmenyaem tolko
otsutstvuyuschie simvoly — bez pravok tvoego broker.py.
# c=a+b
"""
import os, json, urllib.request, urllib.error
from importlib import import_module
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_LLM_AB","A").upper().strip() or "A"
FALLBACK = os.getenv("ESTER_LLM_FALLBACK","0") not in {"0","","false","False"}

def _lmstudio_detect():
    try:
        from modules.lmstudio import detect
        return detect()
    except Exception as e:
        return None

def _call_openai_like(endpoint: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = endpoint.rstrip("/") + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "raw": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.URLError as e:
        return {"ok": False, "reason": f"urlerror: {e}"}
    except Exception as e:
        return {"ok": False, "reason": f"error: {e}"}

def _fallback_chat(messages: List[Dict[str, Any]], **kw) -> Dict[str, Any]:
    cfg = _lmstudio_detect()
    if not cfg:
        return {"ok": False, "reason": "lmstudio_config_missing"}
    payload = {"model": getattr(cfg, "model", "unknown"), "messages": messages, **kw}
    res = _call_openai_like(getattr(cfg, "endpoint", "http://127.0.0.1:1234"), "/v1/chat/completions", payload)
    if res.get("ok"):
        try:
            text = res["raw"]["choices"][0]["message"]["content"]
        except Exception:
            text = None
        return {"ok": True, "model": payload["model"], "reply": text, "raw": res["raw"]}
    return res

def _fallback_complete(prompt: str, **kw) -> Dict[str, Any]:
    cfg = _lmstudio_detect()
    if not cfg:
        return {"ok": False, "reason": "lmstudio_config_missing"}
    payload = {"model": getattr(cfg, "model", "unknown"), "prompt": prompt, **kw}
    res = _call_openai_like(getattr(cfg, "endpoint", "http://127.0.0.1:1234"), "/v1/completions", payload)
    if res.get("ok"):
        try:
            text = res["raw"]["choices"][0]["text"]
        except Exception:
            text = None
        return {"ok": True, "model": payload["model"], "text": text, "raw": res["raw"]}
    return res

def _fallback_embeddings(texts: List[str], **kw) -> Dict[str, Any]:
    cfg = _lmstudio_detect()
    if not cfg:
        return {"ok": False, "reason": "lmstudio_config_missing"}
    payload = {"model": getattr(cfg, "model", "unknown"), "input": texts, **kw}
    res = _call_openai_like(getattr(cfg, "endpoint", "http://127.0.0.1:1234"), "/v1/embeddings", payload)
    return res if res.get("ok") else res

def _install_broker_fallback():
    if not FALLBACK:
        return False
    try:
        broker = import_module("modules.llm.broker")
    except Exception:
        # esli dazhe broker ne importiruetsya — sozdadim minimalnyy «psevdomodul»
        import types
        broker = types.ModuleType("broker")
        import sys
        sys.modules["modules.llm.broker"] = broker  # type: ignore

    # Patchim tolko otsutstvuyuschie funktsii
    if not hasattr(broker, "chat"):
        setattr(broker, "chat", _fallback_chat)
    if not hasattr(broker, "complete"):
        setattr(broker, "complete", _fallback_complete)
    if not hasattr(broker, "embeddings"):
        setattr(broker, "embeddings", _fallback_embeddings)
    if not hasattr(broker, "ping"):
        setattr(broker, "ping", lambda: {"ok": True, "ab": AB, "fallback": True})
    return True

_install_broker_fallback()