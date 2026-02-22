# -*- coding: utf-8 -*-
"""
modules/llm/providers_lmstudio.py — Adapter dlya LM Studio / OpenAI (v1.0+).

Rezhim: Heavy Duty (dlya modeley 32B+ i bolshikh kontekstov).
Integratsiya: Identity Core (Passport) dlya suvereniteta lichnosti.
"""
import os
import logging
import httpx  # Ispolzuem dlya nastroyki taymautov na nizkom urovne
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Importiruem Profile dlya svyazi s lichnostyu (c = a + b)
try:
    from modules.memory import passport
except ImportError:
    passport = None

# Nastroyka loggera
log = logging.getLogger(__name__)

try:
    from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False
    # Zaglushki dlya tipov, chtoby kod ne padal pri importe
    OpenAI = None
    APIError = Exception
    APITimeoutError = Exception
    APIConnectionError = Exception

class LMStudioProvider:
    """
    Provayder dlya lokalnykh LLM s podderzhkoy dlinnykh kontekstov (32k+) i Identity Core.
    """
    def __init__(self):
        self.base_url = os.getenv("LM_STUDIO_API_URL", "http://127.0.0.1:1234/v1")
        self.api_key = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
        self.model = os.getenv("LM_STUDIO_MODEL", "local-model")
        
        # VAZhNO: Taymaut dlya Deep Thinking
        try:
            self.timeout_sec = float(os.getenv("LLM_TIMEOUT", "1200.0"))
        except ValueError:
            self.timeout_sec = 1200.0

        self.client = None
        self._init_client()

    def _init_client(self):
        if not _HAS_OPENAI:
            log.error("[LLM] Oshibka: Biblioteka 'openai' ne ustanovlena.")
            return

        try:
            # Nastraivaem kastomnyy HTTP-transport s gigantskimi taymautami
            http_client = httpx.Client(
                timeout=httpx.Timeout(self.timeout_sec, connect=5.0)
            )

            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                http_client=http_client
            )
            log.info(f"[LLM] Connected to {self.base_url} (Timeout: {self.timeout_sec}s)")
        except Exception as e:
            log.error(f"[LLM] Client Init Failed: {e}")

    def _get_identity_prompt(self) -> str:
        """Poluchaet aktualnyy prompt lichnosti iz profilea."""
        if passport:
            return passport.get_identity()
        return "Ty — Ester, intellektualnaya tsifrovaya sistema. Your owner — Owner."

    def generate(
        self, 
        prompt: str, 
        system_prompt: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = -1,
        **kwargs
    ) -> str:
        """
        Generatsiya otveta s uchetom lichnosti.
        Esli system_prompt ne zadan yavno, ispolzuetsya Identity Core.
        """
        if not self.client:
            self._init_client()
            if not self.client:
                return "[ERROR] LLM Client is offline."

        # LOGIKA LIChNOSTI:
        # Esli sistemnyy prompt pust — zagruzhaem Lichnost (Profile).
        # Esli on zadan (naprimer, dlya summarizatsii teksta) — ispolzuem zadannyy.
        current_system_prompt = system_prompt if system_prompt else self._get_identity_prompt()

        messages = []
        if current_system_prompt:
            messages.append({"role": "system", "content": current_system_prompt})
        
        messages.append({"role": "user", "content": prompt})

        req_params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens > 0:
            req_params["max_tokens"] = max_tokens
        elif max_tokens == -1:
            req_params["max_tokens"] = -1

        # Podmeshivaem dop. parametry
        for k, v in kwargs.items():
            if v is not None:
                req_params[k] = v

        try:
            response = self.client.chat.completions.create(**req_params)
            
            if not response.choices:
                log.warning("[LLM] Empty response from model")
                return ""
            
            content = response.choices[0].message.content
            
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                log.warning("[LLM] Warning: Output truncated (length limit hit).")
                content += "\n[...obryv svyazi...]"
            
            return content

        except APITimeoutError:
            log.error(f"[LLM] Timeout after {self.timeout_sec}s. Deep Thinking took too long.")
            return "[ERROR] Timeout: Mysl byla slishkom glubokoy dlya tekuschego taymauta."
        
        except APIConnectionError:
            log.error(f"[LLM] Connection refused at {self.base_url}. Is LM Studio running?")
            return "[ERROR] Connection Refused: Prover LM Studio."

        except Exception as e:
            log.error(f"[LLM] Unknown generation error: {e}")
            return f"[ERROR] System Error: {e}"

    def smoketest(self) -> str:
        if not self.client: 
            return "FAILED: Library not loaded"
        try:
            # Proverka svyazi
            self.client.models.list()
            # Proverka Profilea
            id_check = "Passport Linked" if passport else "Passport Missing"
            return f"OK (Connected 32B Ready, {id_check})"
        except Exception as e:
            return f"FAILED: {e}"

# Singleton instance
adapter = LMStudioProvider()

# Funktsiya-obertka dlya sovmestimosti
def generate(prompt, system_prompt="", **kwargs):
    return adapter.generate(prompt, system_prompt, **kwargs)