# -*- coding: utf-8 -*-
"""
R4/services/reco/llm_client.py — minimalistichnyy OpenAI-sovmestimyy HTTP-klient dlya LM Studio (/v1/chat/completions).

Mosty:
- Yavnyy: Enderton — protokol kak nabor predikatov nad (url, method, payload) s chetkoy proverkoy uspekha.
- Skrytyy #1: Ashbi — prostoy regulyator: odin POST s taymautom; pri sboyakh — kontroliruemoe povedenie.
- Skrytyy #2: Cover & Thomas — vyzhimaem "signal" (strogiy JSON-otvet) i otbrasyvaem shum (lishniy tekst), trebuya JSON-rezhim.

Zemnoy abzats:
Klient rabotaet tolko na stdlib (`urllib`), bez vneshnikh zavisimostey. Po umolchaniyu stuchitsya k LM Studio
na `http://127.0.0.1:1234/v1/chat/completions`. Esli zapros ne udalsya/taymaut — kidaet isklyuchenie.
Vyzyvayuschaya storona obyazana sdelat avtokatbek (B→A).

# c=a+b
"""
from __future__ import annotations
import json
import os
import ssl
from urllib import request, error
from typing import List, Dict, Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class LMStudioClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or os.environ.get("LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234").rstrip("/")
        self.model = model or os.environ.get("R4_LLM_MODEL") or "local-llm"
        self.timeout = float(os.environ.get("R4_TIMEOUT") or (timeout or 4.0))
        self.endpoint = self.base_url + "/v1/chat/completions"

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 400, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(self.endpoint, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout, context=ssl._create_unverified_context()) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            raise RuntimeError(f"LMStudio HTTP {e.code}: {body[:200]}") from None
        except Exception as e:
            raise RuntimeError(f"LMStudio error: {e}") from None

        try:
            js = json.loads(raw)
            # OpenAI-sovmestimyy otvet
            return (js.get("choices") or [{}])[0].get("message", {}).get("content", "")
        except Exception:
            raise RuntimeError("LMStudio: invalid JSON response")