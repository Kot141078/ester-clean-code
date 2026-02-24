# -*- coding: utf-8 -*-
"""
providers/pool.py — канонический пул провайдеров (local / gemini / gpt4) для Ester.

ЯВНЫЙ МОСТ: c=a+b → человек (a) задаёт режимы/ключи, код (b) гарантирует единый выбор провайдера → узел (c) не распадается на дубли.
СКРЫТЫЕ МОСТЫ:
  - Ashby (кибернетика): variety должно быть управляемым — несколько моделей полезны, но только через один шлюз.
  - Cover & Thomas (инфотеория): канал/бюджет ограничен — облако включаем только при наличии ключей и вне CLOSED_BOX.
ЗЕМНОЙ АБЗАЦ (инженерия/анатомия):
  Этот модуль — как распределительный коллектор в гидросистеме: много источников давления,
  но одна «гребёнка» и один манометр. Иначе начинаются протечки и ложные показания.

Примечание:
- Пул предоставляет AsyncOpenAI-клиенты (OpenAI-compatible API) для локального узла и облаков.
- Поведение cloud-веток автоматически отключается при CLOSED_BOX/LOCAL_ONLY или отсутствии ключа.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

from openai import AsyncOpenAI  # OpenAI python SDK (v1+)
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _env_int(name: str, default: int) -> int:
    try:
        v = str(os.getenv(name, "")).strip()
        if v == "":
            return int(default)
        return int(float(v))
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    try:
        v = str(os.getenv(name, "")).strip()
        if v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _env_str(name: str, default: str = "") -> str:
    try:
        v = os.getenv(name, default)
        return (v or "").strip()
    except Exception:
        return (default or "").strip()


def _env_bool(name: str, default: bool = False) -> bool:
    v = str(os.getenv(name, "")).strip().lower()
    if v == "":
        return bool(default)
    return v in ("1", "true", "yes", "on", "y")


def _has_usable_api_key(raw: str) -> bool:
    v = str(raw or "").strip()
    if not v:
        return False
    up = v.upper()
    bad_exact = {
        "ROTATE_REQUIRED",
        "REPLACE_ME",
        "CHANGE_ME",
        "CHANGEME",
        "YOUR_API_KEY",
        "YOUR_KEY",
        "PLACEHOLDER",
        "NONE",
        "NULL",
    }
    if up in bad_exact:
        return False
    bad_parts = (
        "ROTATE_REQUIRED",
        "REPLACE_ME",
        "PLACEHOLDER",
        "DUMMY",
        "EXAMPLE",
    )
    return not any(p in up for p in bad_parts)


def _first_usable_api_key(*env_names: str) -> str:
    first = ""
    for idx, name in enumerate(env_names):
        v = _env_str(name, "")
        if idx == 0:
            first = v
        if _has_usable_api_key(v):
            return v
    return first


def _norm_url(u: str) -> str:
    u = (u or "").strip()
    return u.rstrip("/") if u else ""


def _derive_gemini_openai_base(gemini_api_base: str) -> str:
    """
    Gemini OpenAI-compatible:
      - если уже /v1beta/openai -> просто гарантируем trailing slash
      - иначе: <base>/v1beta/openai/
    """
    b = (gemini_api_base or "").strip().rstrip("/")
    if "/v1beta/openai" in b:
        return b + "/"
    if b == "":
        b = "https://generativelanguage.googleapis.com"
    return b + "/v1beta/openai/"


def _models_url(base_url: str) -> str:
    b = _norm_url(base_url)
    if b.endswith("/v1"):
        return b + "/models"
    return b + "/v1/models"


def _normalize_model_id(model_id: str) -> str:
    return str(model_id or "").strip().split("/")[-1].lower()


def _fetch_openai_models(base_url: str, timeout_sec: float = 2.5) -> list[str]:
    url = _models_url(base_url)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=float(timeout_sec)) as r:  # noqa: S310 (local endpoint by config)
        raw = r.read().decode("utf-8", errors="ignore")
    payload = json.loads(raw or "{}")
    out: list[str] = []
    for item in (payload.get("data") or []):
        mid = str((item or {}).get("id") or "").strip()
        if mid:
            out.append(mid)
    return out


def _resolve_local_model(base_url: str) -> str:
    pin = _env_str("LMSTUDIO_MODEL_PIN", "")
    if pin:
        return pin

    configured = _env_str("LMSTUDIO_MODEL", "")
    auto_model = _env_bool("LMSTUDIO_AUTO_MODEL", True)
    if not auto_model:
        return configured or "local-model"

    timeout = _env_float("LMSTUDIO_MODEL_DISCOVERY_TIMEOUT_SEC", 2.5)
    try:
        ids = _fetch_openai_models(base_url, timeout_sec=max(0.5, float(timeout)))
    except Exception:
        ids = []

    if ids:
        if configured:
            if configured in ids:
                return configured
            cfg_norm = _normalize_model_id(configured)
            for mid in ids:
                if _normalize_model_id(mid) == cfg_norm:
                    return mid
        return ids[0]

    return configured or "local-model"


# Global guard flags (зеркалим run_ester_fixed.py)
CLOSED_BOX = _env_bool("CLOSED_BOX", False)
LOCAL_ONLY = _env_bool("LOCAL_ONLY", False)
TIMEOUT_CAP = float(os.getenv("TIMEOUT_CAP", "3600"))
_LOG = logging.getLogger("providers.pool")


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    model: str
    max_out_tokens: int
    timeout: float


class ProviderPool:
    """
    Единая точка для провайдеров (local/gemini/gpt4).

    API-совместимость с использованием в run_ester_fixed.py:
      - has(name) -> bool
      - cfg(name) -> ProviderConfig
      - enabled(name) -> bool
      - max_tokens(name) -> Optional[int]
      - client(name) -> AsyncOpenAI
      - reload() / reset_clients()
    """

    _ALIASES = {
        "openai": "gpt4",
        "gpt": "gpt4",
        "gpt-4": "gpt4",
        "gpt4o": "gpt4",
        "oai": "gpt4",
        "gpt-5": "gpt4",
        "gpt-5-mini": "gpt4",
        "gpt-4o": "gpt4",
        "gpt-4o-mini": "gpt4",
        "gpt-4.1-mini": "gpt4",
    }

    def __init__(self) -> None:
        self._clients: Dict[str, AsyncOpenAI] = {}
        self._cfg: Dict[str, ProviderConfig] = {}
        self._last_local_model_refresh_ts = 0.0
        self._local_model_refresh_sec = 30
        self._local_model_auto = True
        self.reload()

    def _canon_name(self, name: str) -> str:
        n = (name or "").strip().lower()
        return self._ALIASES.get(n, n)

    def reload(self) -> None:
        """
        Перечитать env и пересобрать конфиги.
        Клиенты не пересоздаём автоматически — вызови reset_clients()
        если хочешь применить новые URL/keys в рантайме.
        """
        local_base = _norm_url(_env_str("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"))
        gemini_base = _derive_gemini_openai_base(_env_str("GEMINI_API_BASE", ""))
        openai_base = _norm_url(_env_str("OPENAI_API_BASE", "https://api.openai.com/v1"))
        gemini_key = _first_usable_api_key("GEMINI_API_KEY", "GOOGLE_API_KEY", "ESTER_GEMINI_API_KEY")
        openai_key = _first_usable_api_key("OPENAI_API_KEY", "ESTER_OPENAI_API_KEY")
        local_model = _resolve_local_model(local_base)

        ctx_tokens = _env_int("LMSTUDIO_CONTEXT_WINDOW_TOKENS", _env_int("LMSTUDIO_CTX_WINDOW_TOKENS", 37500))
        reserve = _env_int("LMSTUDIO_CONTEXT_RESERVE_TOKENS", 6000)
        local_hard_limit = max(256, int(ctx_tokens) - max(256, int(reserve)))
        req_local_max = _env_int("LOCAL_MAX_OUT_TOKENS", min(4096, local_hard_limit))
        local_max_out = local_hard_limit if req_local_max <= 0 else min(req_local_max, local_hard_limit)
        self._local_model_refresh_sec = max(5, _env_int("LMSTUDIO_MODEL_REFRESH_SEC", 30))
        self._local_model_auto = _env_bool("LMSTUDIO_AUTO_MODEL", True)

        self._cfg = {
            "local": ProviderConfig(
                name="local",
                base_url=local_base,
                api_key="lm-studio",
                model=local_model,
                max_out_tokens=local_max_out,
                timeout=min(_env_float("LOCAL_TIMEOUT", 600.0), float(TIMEOUT_CAP)),
            ),
            "gemini": ProviderConfig(
                name="gemini",
                base_url=_norm_url(gemini_base),
                api_key=gemini_key,
                model=_env_str("GEMINI_MODEL", "gemini-1.5-flash"),
                max_out_tokens=_env_int("GEMINI_MAX_OUT_TOKENS", 8192),
                timeout=min(_env_float("GEMINI_TIMEOUT", 120.0), float(TIMEOUT_CAP)),
            ),
            "gpt4": ProviderConfig(
                name="gpt4",
                base_url=openai_base,
                api_key=openai_key,
                model=_env_str("OPENAI_MODEL", "gpt-4o"),
                max_out_tokens=_env_int("OPENAI_MAX_OUT_TOKENS", 16384),
                timeout=min(_env_float("OPENAI_TIMEOUT", 120.0), float(TIMEOUT_CAP)),
            ),
        }

    def _maybe_refresh_local_model(self) -> None:
        if not self._local_model_auto:
            return
        now = time.time()
        if (now - float(self._last_local_model_refresh_ts)) < float(self._local_model_refresh_sec):
            return
        self._last_local_model_refresh_ts = now
        cfg = self._cfg.get("local")
        if not cfg:
            return
        try:
            selected = _resolve_local_model(cfg.base_url)
        except Exception:
            return
        if selected and selected != cfg.model:
            cfg.model = selected
            try:
                _LOG.info("[PROVIDERS] local model auto-selected: %s", selected)
            except Exception:
                pass

    def reset_clients(self) -> None:
        self._clients = {}

    def init(self) -> None:
        return

    def has(self, name: str) -> bool:
        name = self._canon_name(name)
        return name in self._cfg

    def cfg(self, name: str) -> ProviderConfig:
        name = self._canon_name(name)
        if name == "local":
            self._maybe_refresh_local_model()
        if name not in self._cfg:
            raise KeyError(f"Unknown provider: {name}")
        return self._cfg[name]

    def enabled(self, name: str) -> bool:
        """
        local — всегда доступен.
        cloud — только если есть ключ и не включён режим закрытого бокса.
        """
        name = self._canon_name(name)
        cfg = self._cfg.get(name)
        if not cfg:
            return False

        if CLOSED_BOX or LOCAL_ONLY:
            return (cfg.name == "local")

        if cfg.name == "local":
            return True

        return _has_usable_api_key(cfg.api_key)

    def max_tokens(self, name: str) -> Optional[int]:
        cfg = self.cfg(name)
        try:
            m = int(cfg.max_out_tokens)
            return None if m <= 0 else m
        except Exception:
            return None

    def timeout_for_channel(self, name: str, channel: str = "default") -> float:
        """
        Effective timeout with optional channel-specific cap.
        Examples:
          ESTER_PROVIDER_TIMEOUT_WEB_SEC=8
          ESTER_PROVIDER_TIMEOUT_TELEGRAM_SEC=25
          ESTER_PROVIDER_TIMEOUT_DREAM_SEC=40
        """
        cfg = self.cfg(name)
        base = float(getattr(cfg, "timeout", 0.0) or 0.0)
        ch = str(channel or "").strip().lower()
        if not ch or ch in {"default", "unknown"}:
            return max(0.8, base) if base > 0 else 8.0
        key = f"ESTER_PROVIDER_TIMEOUT_{ch.upper()}_SEC"
        cap = _env_float(key, 0.0)
        if cap <= 0.0:
            return max(0.8, base) if base > 0 else 8.0
        if base <= 0.0:
            return max(0.8, float(cap))
        return max(0.8, min(float(base), float(cap)))

    def client(self, name: str) -> AsyncOpenAI:
        name = self._canon_name(name)

        if name not in self._clients:
            cfg = self.cfg(name)

            if cfg.name != "local" and not self.enabled(name):
                raise RuntimeError(f"Provider disabled (missing key or CLOSED_BOX): {name}")

            self._clients[name] = AsyncOpenAI(
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                timeout=float(cfg.timeout),
            )

        return self._clients[name]


PROVIDERS = ProviderPool()
