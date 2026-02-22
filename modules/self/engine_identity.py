from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
# modules/self/engine_identity.py
# Identifikatsiya "motora" myshleniya.
# c=a+b

def engine_label(engine_id: str) -> str:
    """Vozvraschaet cheloveko-chitaemoe opisanie tekuschego dvizhka."""
    # Slovar realnykh podklyucheniy. Lishnee ubrano.
    mapping = {
        "lmstudio": "lokalnaya LM Studio",
        "lmstudio_ctx": "lokalnaya LM Studio (fast/ctx-budget)",
        "lmstudio_full": "lokalnaya LM Studio (deep/full-ctx)",
        "gemini_fallback": "oblachnyy Gemini (CLOUD FALLBACK)",
        "openai_main": "OpenAI GPT-4o"
    }
    # Esli tochnogo sovpadeniya net, vozvraschaem ID kak est
    return mapping.get(engine_id, engine_id)