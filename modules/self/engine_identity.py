from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
# modules/self/engine_identity.py
# Identification of the "motor" of thinking.
# c=a+b

def engine_label(engine_id: str) -> str:
    """Returns a human-readable description of the current engine."""
    # Dictionary of real connections. The excess has been removed.
    mapping = {
        "lmstudio": "lokalnaya LM Studio",
        "lmstudio_ctx": "lokalnaya LM Studio (fast/ctx-budget)",
        "lmstudio_full": "lokalnaya LM Studio (deep/full-ctx)",
        "gemini_fallback": "oblachnyy Gemini (CLOUD FALLBACK)",
        "openai_main": "OpenAI GPT-4o"
    }
    # If there is no exact match, return the ID as is
    return mapping.get(engine_id, engine_id)