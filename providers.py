# -*- coding: utf-8 -*-
"""
Provider Registry for LLM: reestr provayderov (local/cloud/judge).
Sovmestimo s kanonom: klass ProviderRegistry s metodami status(), select(), generate().
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class ProviderError(Exception):
    pass


class ProviderRegistry:
    def __init__(self):
        # Aktivnyy rezhim: local | cloud | judge
        self._mode = os.getenv("DEFAULT_MODE", "judge")
        # Konfiguratsii endpointov
        self.local_url = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:1234/v1/chat/completions")
        self.cloud_url = os.getenv("CLOUD_LLM_URL", "https://api.openai.com/v1/chat/completions")
        self.cloud_model = os.getenv("CLOUD_LLM_MODEL", "gpt-4o-mini")
        self.cloud_api_key = os.getenv("OPENAI_API_KEY", "")
        # Judge — kto sinteziruet finalnyy otvet (cloud po umolchaniyu)
        self.judge_model = os.getenv("JUDGE_MODEL", self.cloud_model)
        self.judge_url = os.getenv("JUDGE_URL", self.cloud_url)

    # --- upravlenie ---
    def status(self) -> Dict[str, Any]:
        return {
            "active": self._mode,
            "providers": {
                "local": {"url": self.local_url},
                "cloud": {"url": self.cloud_url, "model": self.cloud_model},
                "judge": {"url": self.judge_url, "model": self.judge_model},
            },
        }

    def select(self, mode: str) -> Dict[str, Any]:
        mode = mode.strip().lower()
        if mode not in {"local", "cloud", "judge"}:
            raise ProviderError(f"unknown mode: {mode}")
        self._mode = mode
        return {"ok": True, "active": self._mode}

    # --- generatsiya ---
    def _headers_cloud(self) -> Dict[str, str]:
        if not self.cloud_api_key:
            raise ProviderError("OPENAI_API_KEY is empty")
        return {"Authorization": f"Bearer {self.cloud_api_key}"}

    def _req_local(self, prompt: str, temperature: float = 0.3) -> str:
        try:
            payload = {
                "model": "local-model",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": False,
            }
            r = requests.post(self.local_url, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            # Folbek — vozvrat podskazki s metkoy
            return f"[local-fallback] {prompt}"

    def _req_cloud(self, prompt: str, model: Optional[str] = None, temperature: float = 0.3) -> str:
        try:
            payload = {
                "model": model or self.cloud_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": False,
            }
            r = requests.post(
                self.cloud_url, json=payload, headers=self._headers_cloud(), timeout=60
            )
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return f"[cloud-fallback] {prompt}"

    def _req_judge(self, prompt: str, candidates: List[str], temperature: float = 0.2) -> str:
        # Judge poluchaet spisok alternativ i formiruet finalnyy otvet
        merged = "\n\n".join(f"[CANDIDATE {i+1}]\n{c}" for i, c in enumerate(candidates))
        judge_prompt = f"Sinteziruy luchshiy otvet iz kandidatov. Vzves plyusy/minusy i day edinyy itog.\n\nVopros: {prompt}\n\nKandidaty:\n{merged}"
        return self._req_cloud(judge_prompt, model=self.judge_model, temperature=temperature)

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        mode = self._mode
        if mode == "local":
            return self._req_local(prompt, temperature=temperature)
        elif mode == "cloud":
            return self._req_cloud(prompt, temperature=temperature)
        # judge: parallelnyy zapros v local+cloud s sintezom
        local = self._req_local(prompt, temperature=temperature)
        cloud = self._req_cloud(prompt, temperature=temperature)
# return self._req_judge(prompt, [local, cloud], temperature=0.2)