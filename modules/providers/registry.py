# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
import os
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Importiruem adaptery (bezopasno)
try:
    from .openai_adapter import send_chat as _send_openai
except ImportError:
    _send_openai = None

try:
    from .lmstudio_adapter import send_chat as _send_lmstudio
except ImportError:
    _send_lmstudio = None

try:
    from .gemini_adapter import send_chat as _send_gemini
except ImportError:
    _send_gemini = None

log = logging.getLogger(__name__)

# Profile
try:
    from modules.mem import passport as mem_passport
except ImportError:
    mem_passport = None

def _ensure_identity(messages):
    # If there are already systems, don’t touch them
    if messages and messages[0].get("role") == "system":
        return messages
    
    sys_prompt = "Ty — Ester. Your owner — Owner."
    if mem_passport:
        try:
            sys_prompt = mem_passport.get_identity_system_prompt()
        except Exception: pass
        
    messages.insert(0, {"role": "system", "content": sys_prompt})
    return messages


def select_provider(mode: str | None = None) -> Dict[str, Any]:
    """Returns a compact description of the selected provider.
    Minimum contract for rute/providers_probe.po."""
    m = (mode or "judge").lower()
    name = "unknown"
    sender = None

    if m in ("local", "lmstudio"):
        sender = _send_lmstudio
        name = "lmstudio"
    elif m in ("cloud", "openai", "gpt"):
        sender = _send_openai
        name = "openai"
    elif m == "gemini":
        sender = _send_gemini
        name = "gemini"
    elif m in ("judge", "auto"):
        if _send_openai:
            sender = _send_openai
            name = "openai"
        elif _send_gemini:
            sender = _send_gemini
            name = "gemini"
        elif _send_lmstudio:
            sender = _send_lmstudio
            name = "lmstudio"
    if not sender and _send_lmstudio:
        sender = _send_lmstudio
        name = "lmstudio"

    return {"name": name, "sender": sender}

def answer(messages: List[Dict[str, str]], mode: str = None, **kw) -> Dict[str, Any]:
    # 1. Garantiruem profile
    messages = _ensure_identity(messages)
    
    mode = (mode or "judge").lower()
    
    # 2. Provider selection logic (Simplified and Reliable)
    sender = None
    provider_name = "unknown"

    # Explicit Modes
    if mode in ["local", "lmstudio"]:
        sender = _send_lmstudio
        provider_name = "lmstudio"
    elif mode in ["cloud", "openai", "gpt"]:
        sender = _send_openai
        provider_name = "openai"
    elif mode == "gemini":
        sender = _send_gemini
        provider_name = "gemini"
    
    # JUJE / AUTO mode (We try everything)
    elif mode in ["judge", "auto"]:
        if _send_openai: 
            sender = _send_openai
            provider_name = "openai (judge)"
        elif _send_gemini:
            sender = _send_gemini
            provider_name = "gemini (judge)"
        elif _send_lmstudio:
            sender = _send_lmstudio
            provider_name = "lmstudio (judge)"
    
    # If the driver is not found
    if not sender:
        # Emergency fullback for at least something
        if _send_lmstudio: 
            sender = _send_lmstudio
            provider_name = "lmstudio (fallback)"
        else:
            return {"ok": False, "error": f"No providers available for mode '{mode}'", "provider": "none"}

    # 3. Otpravka
    try:
        res = sender(messages, **kw)
        # If the dictionary is returned with an error
        if isinstance(res, dict) and not res.get("ok"):
            return res 
            
        text = res.get("text") or res.get("reply") or res.get("answer") or ""
        return {"ok": True, "text": text, "reply": text, "provider": provider_name}

    except Exception as e:
        log.exception(f"Provider {provider_name} crashed")
        return {"ok": False, "error": str(e), "provider": provider_name}
