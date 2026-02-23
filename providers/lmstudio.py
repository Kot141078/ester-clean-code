# -*- coding: utf-8 -*-
from __future__ import annotations

import typing as t

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class LMStudioClient:
    """
    LM Studio (lokalnyy OpenAI-sovmestimyy server)
    Po umolchaniyu rabotaet na http://127.0.0.1:1234/v1
    """

    name = "lmstudio"

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> t.Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_models(self) -> t.List[str]:
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=5)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "data" in data:
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            # nekotorye sborki LM Studio vozvraschayut srazu list
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return []

    def chat(
        self,
        messages: t.List[t.Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: t.Optional[int] = None,
        **kwargs: t.Any,
    ) -> t.Dict[str, t.Any]:
        payload: t.Dict[str, t.Any] = {
            "model": model or kwargs.get("model") or "",
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        # sovmestim s OpenAI Chat Completions
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json()
        text = ""
        try:
            text = raw["choices"][0]["message"]["content"]
        except Exception:
            pass
        usage = raw.get("usage") or {}
        used_model = raw.get("model") or payload["model"]
# return {"text": text, "model": used_model, "usage": usage, "raw": raw}