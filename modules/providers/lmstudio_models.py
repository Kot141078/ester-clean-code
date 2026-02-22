# -*- coding: utf-8 -*-
"""
Avtovybor modeli LM Studio iz /v1/models.

MOSTY:
- (Yavnyy) pick_default_model(base) → str — luchshaya dostupnaya model.
- (Skrytyy #1) Uvazhaet LMSTUDIO_MODEL (env) i data/runtime/model.txt.
- (Skrytyy #2) Rabotaet i s massivami id vida "org/model" i prosto "model".

ZEMNOY ABZATs:
Eto «pereklyuchatel nasadok»: esli polzovatel ne ukazal bit, berem samuyu podkhodyaschuyu nasadku.

# c=a+b
"""
from __future__ import annotations
import os
from typing import List, Optional, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _pin_runtime() -> str | None:
    p = os.path.join("data", "runtime", "model.txt")
    try:
        if os.path.isfile(p):
            val = (open(p, "r", encoding="utf-8").read() or "").strip()
            return val or None
    except Exception:
        pass
    return None

def _normalize(mid: str) -> str:
    # "openai/gpt-oss-20b" → "gpt-oss-20b"
    return mid.split("/")[-1].strip().lower()

def _rank(models: List[str]) -> List[str]:
    # Prostaya evristika predpochteniy
    prefs = [
        "qwq", "qwen3", "qwen2.5-vl", "qwen2.5-72b", "qwen2.5-32b", "qwen3-coder-30b",
        "qwen2.5-14b", "qwen2.5-7b", "deepseek-v2", "gpt-oss-20b",
        "wizardcoder", "codellama", "saiga", "rugpt"
    ]
    scored = []
    for m in models:
        ml = _normalize(m)
        score = 1000
        for i, p in enumerate(prefs):
            if p in ml:
                score = i
                break
        # predpochtem «instruct/chat»
        if "instruct" in ml or "chat" in ml:
            score -= 0.3
        scored.append((score, m))
    scored.sort(key=lambda x: x[0])
    return [m for _, m in scored]

def pick_default_model(base: str = "http://127.0.0.1:1234") -> str:
    # 1) ruchnoy override
    for k in ("LMSTUDIO_MODEL",):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    # 2) runtime-pin
    pin = _pin_runtime()
    if pin:
        return pin
    # 3) iz /v1/models
    import requests  # type: ignore
    url = base.rstrip("/") + "/v1/models"
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    j = r.json()
    ids = [item.get("id") for item in j.get("data", []) if item.get("id")]
    ids = _rank(ids) or ["gpt-oss-20b"]
    return ids[0]


def _runtime_path() -> str:
    return os.path.join("data", "runtime", "model.txt")


def _base_url() -> str:
    envs = [
        os.getenv("LMSTUDIO_ENDPOINTS", ""),
        os.getenv("LMSTUDIO_BASE_URL", ""),
        os.getenv("LMSTUDIO_BASE", ""),
        os.getenv("LLM_API_BASE", ""),
    ]
    for v in envs:
        v = (v or "").strip()
        if not v:
            continue
        # endpoints may be ; separated
        return v.split(";")[0].strip().rstrip("/")
    return "http://127.0.0.1:1234"


def list_models() -> List[str]:
    """Vozvraschaet spisok modeley iz /v1/models (LM Studio / OpenAI-compatible)."""
    try:
        import requests  # type: ignore
        url = _base_url() + "/v1/models"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        j = r.json()
        ids = [item.get("id") for item in j.get("data", []) if item.get("id")]
        return _rank(ids)
    except Exception:
        return []


def get_preferred_model() -> Optional[str]:
    """Vozvraschaet predpochitaemuyu model (env > runtime pin)."""
    for k in ("ESTER_LMSTUDIO_MODEL", "LMSTUDIO_MODEL"):
        v = (os.getenv(k) or "").strip()
        if v:
            return v
    return _pin_runtime()


def set_preferred_model(model: str) -> bool:
    """Sokhranyaet predpochtenie v data/runtime/model.txt."""
    model = (model or "").strip()
    if not model:
        return False
    try:
        p = _runtime_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(model)
        return True
    except Exception:
        return False
# c=a+b
