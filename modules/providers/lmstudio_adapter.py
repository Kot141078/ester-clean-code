# -*- coding: utf-8 -*-
"""modules/providers/lmstudio_adapter.py — LM Studio (OpenAI-compatible) adapter for openai>=1.0.0

Trebovanie: paket openai versii >= 1.0.0 (novyy klientskiy API).

ENV:
- LMSTUDIO_BASE_URL (default: http://127.0.0.1:1234/v1)
- LMSTUDIO_API_KEY (default: lm-studio) # LM Studio obychno ne proveryaet klyuch, no biblioteke nuzhen.
- LMSTUDIO_MODEL (default: local-model)
- LMSTUDIO_TIMEOUT_S (default: 60)

Mosty:
- Yavnyy (Kibernetika ↔ API): edinyy kontrolnyy vkhod (messages) → izmerimyy vykhod (text + usage).
- Skrytyy 1 (Logika ↔ Sovmestimost): adapter pryachet change SDK (v0.28 → v1.x) from other codes.
- Skrytyy 2 (Infoteoriya ↔ Stoimost): temperatura/max_tokens/stream — eto regulyatory “kanala”.

Zemnoy abzats:
V elektrotekhnike ne menyayut vsyu provodku iz-za novoy vilki - stavyat perekhodnik. Tut to zhe same:
openai>=1.0.0 pomenyal interfeys, my stavim adapter, chtoby sistema prodolzhala rabotat,
a ne "sypalas" ot kazhdoy versii SDK.

# c=a+b"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from modules.providers import ProviderResult, register
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name, default)
    return (v or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except Exception:
        return default


def _load_openai_client():
    """Returns (client, err_str). If there is no openay - client = None and err_str."""
    try:
        # openai>=1.0.0
        from openai import OpenAI  # type: ignore

        base_url = _env_str("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
        api_key = _env_str("LMSTUDIO_API_KEY", "lm-studio")

        client = OpenAI(base_url=base_url, api_key=api_key)
        return client, ""
    except Exception as e:  # noqa: BLE001
        return None, f"{e.__class__.__name__}: {e}"


class LMStudioAdapter:
    name = "lmstudio"

    def __init__(self) -> None:
        self.base_url = _env_str("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
        self.model_default = _env_str("LMSTUDIO_MODEL", "local-model")
        self.timeout_s = float(_env_int("LMSTUDIO_TIMEOUT_S", 60))
        self._client, self._client_err = _load_openai_client()

    def send_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> ProviderResult:
        """messages: standard OpenAI chat: [{"role":"system|user|assistant", "content":"..."}]
        kwargs (optional):
          - temperature (float)
          - max_tokens (int)
          - top_p (float)
          - stream (bool) # stream podderzhim pozzhe pri neobkhodimosti; seychas False."""
        if self._client is None:
            return ProviderResult(
                ok=False,
                error=f"openai_lib_missing_or_bad: {self._client_err}",
                provider=self.name,
                model=model or self.model_default,
                meta={"base_url": self.base_url},
            )

        model_id = model or self.model_default
        temperature = float(kwargs.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", None)
        top_p = kwargs.get("top_p", None)
        stream = bool(kwargs.get("stream", False))

        # Stream: in most integrations, Esther expects a solid text.
        # If necessary, we will create a generator/callback.
        if stream:
            log.warning("LMStudioAdapter: stream=True not supported in send_chat(); forced to stream=False")
            stream = False

        log.info("LM Studio Request -> %s (model=%s)", self.base_url, model_id)

        try:
            # openai>=1.0.0
            resp = self._client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=False,
                timeout=self.timeout_s,
            )
            # Novyy SDK vozvraschaet obekt s atributami
            content = ""
            try:
                content = (resp.choices[0].message.content or "").strip()
            except Exception:
                content = ""

            usage = {}
            try:
                # seating may not be available on some compatible servers
                u = getattr(resp, "usage", None)
                if u:
                    usage = {
                        "prompt_tokens": getattr(u, "prompt_tokens", None),
                        "completion_tokens": getattr(u, "completion_tokens", None),
                        "total_tokens": getattr(u, "total_tokens", None),
                    }
            except Exception:
                usage = {}

            return ProviderResult(
                ok=True,
                text=content,
                reply=content,
                provider=self.name,
                model=model_id,
                raw=None,  # so as not to drag a heavy object into ZhSON
                meta={"base_url": self.base_url, "usage": usage},
            )

        except Exception as e:  # noqa: BLE001
            log.error("LM Studio Failed: %s", e)
            return ProviderResult(
                ok=False,
                error=f"{e.__class__.__name__}: {e}",
                provider=self.name,
                model=model_id,
                meta={"base_url": self.base_url},
            )

    def send_embeddings(self, texts: List[str], model: Optional[str] = None, **kwargs: Any) -> Any:
        """Embeddings via OpenAI-compatible endpoint.
        Not all local LM Studio models support this - if not, the server will return an error."""
        if self._client is None:
            raise RuntimeError(f"openai_lib_missing_or_bad: {self._client_err}")

        model_id = model or _env_str("LMSTUDIO_EMBED_MODEL", self.model_default)
        resp = self._client.embeddings.create(
            model=model_id,
            input=texts,
            timeout=self.timeout_s,
        )
        # Vernem v «legkom» vide
        return {
            "model": model_id,
            "data": [{"index": d.index, "embedding": d.embedding} for d in resp.data],
        }


# Registry hook
def _factory() -> LMStudioAdapter:
    return LMStudioAdapter()


register("lmstudio", _factory)


# Butler-compatiable function name (if the old code imports send_chat from the adapter)
def send_chat(messages: List[Dict[str, Any]], model: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    return _factory().send_chat(messages, model=model, **kwargs).as_dict()