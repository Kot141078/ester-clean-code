# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def provider_info_skill() -> Dict[str, Any]:
    """
    Svodka po LLM-provayderam i konfigu.
    """
    info: Dict[str, Any] = {"status": "ok"}

    try:
        from modules import providers  # type: ignore
        info["providers"] = providers.list_providers()  # type: ignore
    except Exception as e:
        info["providers_error"] = str(e)

    info["env"] = {
        "LLM_DEFAULT_PROVIDER": os.getenv("LLM_DEFAULT_PROVIDER", "lmstudio"),
        "LMSTUDIO_BASE_URL": os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    }
    return info