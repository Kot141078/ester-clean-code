# -*- coding: utf-8 -*-
"""Public-safe capability router for local multimodal runtime profiles.

The router is intentionally configuration-only. It does not read private
memory, tokens, logs, vector stores, payload dumps, or machine-specific paths.
"""

from __future__ import annotations

import os
from typing import Any, Dict


VISION_MODEL_DEFAULT = "qwen2.5vl:7b"
VISION_MARKERS = ("vl", "vision", "llava", "minicpm", "internvl", "omni")


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _truthy(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    if raw == "":
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except Exception:
        return int(default)


def chat_model() -> str:
    return (
        _env("ESTER_CHAT_MODEL")
        or _env("LMSTUDIO_MODEL")
        or _env("OLLAMA_PROXY_DEFAULT_MODEL")
        or "local-model"
    )


def vision_model() -> str:
    return _env("ESTER_VISION_MODEL") or _env("VISION_MODEL") or VISION_MODEL_DEFAULT


def vision_provider() -> str:
    return (_env("ESTER_VISION_PROVIDER") or _env("VISION_MODE") or "local").lower()


def vision_max_tokens() -> int:
    return _int_env("ESTER_VISION_MAX_TOKENS", 1200)


def is_vision_model(model: str) -> bool:
    name = str(model or "").lower()
    return any(marker in name for marker in VISION_MARKERS)


def dream_model() -> str:
    return _env("ESTER_DREAM_MODEL") or chat_model()


def fast_model() -> str:
    return _env("ESTER_FAST_MODEL") or chat_model()


def route_for(kind: str) -> Dict[str, Any]:
    key = str(kind or "text").strip().lower()
    if key in {"image", "photo", "vision", "picture"}:
        return {
            "kind": "image",
            "provider": vision_provider(),
            "model": vision_model(),
            "stage": "vision_model_to_description_to_chat_model",
            "max_tokens": vision_max_tokens(),
        }
    if key in {"speech", "voice", "audio"}:
        return {
            "kind": "speech",
            "stt": stt_status(),
            "chat": {"provider": _env("LLM_DEFAULT_PROVIDER", "local"), "model": chat_model()},
            "tts": tts_status(),
            "stage": "stt_to_chat_model_to_tts",
        }
    if key in {"dream", "long", "thinking", "reflection"}:
        return {
            "kind": "long_thinking",
            "provider": _env("DREAM_PROVIDER") or _env("LLM_DEFAULT_PROVIDER", "local"),
            "model": dream_model(),
            "max_tokens": _int_env("DREAM_MAX_TOKENS", _int_env("MAX_OUT_TOKENS", 6000)),
        }
    if key in {"fast", "reaction", "reflex"}:
        return {
            "kind": "fast_reaction",
            "provider": _env("ESTER_FAST_PROVIDER") or _env("LLM_DEFAULT_PROVIDER", "local"),
            "model": fast_model(),
            "max_tokens": _int_env("ESTER_FAST_MAX_TOKENS", 1800),
        }
    return {
        "kind": "text",
        "provider": _env("LLM_DEFAULT_PROVIDER", "local"),
        "model": chat_model(),
        "max_tokens": _int_env("ESTER_CHAT_MAX_TOKENS", _int_env("MAX_OUT_TOKENS", 6000)),
    }


def stt_status() -> Dict[str, Any]:
    return {
        "enabled": _truthy("STT_ENABLE", False),
        "model": _env("STT_MODEL", "base"),
        "model_path_configured": bool(_env("ESTER_STT_MODEL_PATH")),
        "device": _env("STT_DEVICE", "cpu"),
        "compute_type": _env("STT_COMPUTE_TYPE", "int8"),
        "language": _env("STT_LANG", "en"),
        "allow_remote_init": _truthy("ESTER_STT_ALLOW_REMOTE_INIT", False),
    }


def tts_status() -> Dict[str, Any]:
    return {
        "enabled": _truthy("ESTER_TTS_ENABLED", True),
        "telegram_command_enabled": _truthy("ESTER_TG_TTS_COMMAND_ENABLED", False),
        "engine_preference": _env("TTS_ENGINE_PREFERENCE", "edge-tts,coqui-tts,espeak,pyttsx3,tone"),
        "default_voice": _env("TTS_VOICE_DEFAULT", "default"),
        "http_route": "/studio/tts/say",
    }


def status() -> Dict[str, Any]:
    return {
        "ok": True,
        "profile": _env("ESTER_CAPABILITY_PROFILE", "local-multimodal"),
        "routes": {
            "text": route_for("text"),
            "image": route_for("image"),
            "speech": route_for("speech"),
            "dream": route_for("dream"),
            "fast": route_for("fast"),
        },
        "preload": {
            "vision": _truthy("ESTER_VISION_PRELOAD", False),
            "vision_keep_alive": _env("ESTER_VISION_KEEP_ALIVE", "-1"),
        },
    }
