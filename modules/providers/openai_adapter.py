# -*- coding: utf-8 -*-
"""OpenAI-sovmestimyy adapter: rabotaet i s OpenAI, i s LM Studio (cherez OPENAI_API_BASE).

MOSTY:
- (Yavnyy) send_chat(messages, model=..., temperature=..., max_tokens=...) → {'ok','text','provider'}.
- (Skrytyy #1) Esli OPENAI_API_BASE ukazyvaet na LM Studio (LMSTUDIO_BASE), provayder=lmstudio.
- (Skrytyy #2) Esli model ne zadana - berem LMSTUDIO_MODEL / runtime pin / avto-vybor iz /v1/models.

ZEMNOY ABZATs:
Odin HTTP format → dva mira: oblako i lokal. Menyaem tolko BASE, ostalnoe - odinakovo.

# c=a+b"""
from __future__ import annotations
import os, json
from typing import List, Dict, Any, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _base_and_provider() -> (str, str):
    # priority explicit OPENAY_API_BASE; otherwise LM Studio
    lm = (os.getenv("LMSTUDIO_BASE") or "http://127.0.0.1:1234").rstrip("/")
    base = (os.getenv("OPENAI_API_BASE") or lm).rstrip("/")
    provider = "lmstudio" if base == lm else "openai"
    return base, provider

def _pick_model(default_provider: str, hint: Optional[str]) -> str:
    if hint:
        return hint
    # env-navodki
    for k in ("OPENAI_MODEL", "GPT_MODEL"):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    # LM Studio avto-vybor
    if default_provider == "lmstudio":
        try:
            from .lmstudio_models import pick_default_model
            return pick_default_model(os.getenv("LMSTUDIO_BASE") or "http://127.0.0.1:1234")
        except Exception:
            pass
    # reasonable default for the cloud
    return "gpt-4o-mini"

def send_chat(messages: List[Dict[str, str]],
              model: Optional[str] = None,
              temperature: float = 0.2,
              max_tokens: int = 512) -> Dict[str, Any]:
    base, provider = _base_and_provider()
    mdl = _pick_model(provider, model)

    url = base + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    # Any non-empty value is suitable for LM Studio; OpenAI requires a real key
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LMSTUDIO_API_KEY") or "lm-studio"
    headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": mdl,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        import requests  # type: ignore
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        j = r.json()
        text = j["choices"][0]["message"]["content"]
        return {"ok": True, "text": text, "provider": provider, "model": mdl}
    except Exception as e:
        # fullback - “echo”, but does not crash the server
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        note = f"{provider} error: {e}"
        return {"ok": True, "text": last_user, "provider": "echo", "note": note, "model": mdl}
# c=a+b