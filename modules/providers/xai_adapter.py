# -*- coding: utf-8 -*-
"""
modules/providers/xai_adapter.py — dostup k xAI (OpenAI-sovmestimyy stil).

MOSTY:
- (Yavnyy) send_chat(messages) — kontrakt kak u openai_adapter.
- (Skrytyy #1) Esli xAI nedostupen — folbek na OpenAI-sovmestimyy adapter (v t.ch. LM Studio).
- (Skrytyy #2) Uvazhaet XAI_API_KEY/XAI_BASE_URL i XAI_MODEL_NAME.

ZEMNOY ABZATs:
Odin shnur → lyubye rozetki: obschaya vilka dlya raznykh provayderov.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import List, Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def send_chat(messages: List[Dict[str, str]],
              model: Optional[str] = None,
              temperature: float = 0.2,
              max_tokens: int = 512) -> Dict[str, Any]:
    api_key = os.getenv("XAI_API_KEY", "")
    base_url = (os.getenv("XAI_BASE_URL") or "https://api.x.ai").rstrip("/")
    mdl = model or os.getenv("XAI_MODEL_NAME") or "grok-4-latest"
    try:
        import requests  # type: ignore
        url = base_url + "/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": mdl, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        j = r.json()
        text = j["choices"][0]["message"]["content"]
        return {"ok": True, "text": text, "provider": "xai", "model": mdl}
    except Exception:
        # Folbek — LM Studio/echo cherez OpenAI-sovmestimyy adapter
        from .openai_adapter import send_chat as _openai_like
        return _openai_like(messages, model=mdl, temperature=temperature, max_tokens=max_tokens)
# c=a+b