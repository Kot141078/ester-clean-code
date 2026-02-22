# -*- coding: utf-8 -*-
"""
modules.llm.autoconfig_settings — konfig LLM + detekt/sokhranenie.
# c=a+b
"""
from __future__ import annotations
import os, json
from dataclasses import dataclass
from pathlib import Path
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

@dataclass
class LLMConfig:
    endpoint: str = "http://127.0.0.1:1234/v1"
    api_key: str = "lm-studio"
    model: str = "qwen2.5-coder:latest"

def load_llm_settings() -> dict:
    return {
        "endpoint": os.getenv("LMSTUDIO_URL") or os.getenv("OPENAI_API_BASE") or LLMConfig.endpoint,
        "api_key": os.getenv("OPENAI_API_KEY") or LLMConfig.api_key,
        "model":   os.getenv("JUDGE_MODEL") or os.getenv("OPENAI_MODEL") or LLMConfig.model
    }

def save_llm_settings(cfg: dict) -> bool:
    base = os.getenv("PERSIST_DIR") or os.path.join(os.getcwd(), "data")
    p = Path(base) / "config" / "llm_settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg or {}, f, ensure_ascii=False, indent=2)
    return True

def detect_local_llm() -> dict:
    endpoint = os.getenv("LMSTUDIO_URL") or LLMConfig.endpoint
    model = os.getenv("LMSTUDIO_MODEL") or os.getenv("JUDGE_MODEL") or LLMConfig.model
    return {"endpoint": endpoint, "model": model, "ok": True}