# -*- coding: utf-8 -*-
"""modules/llm/providers_gemini.po - Adapter for Google Gemini API.

Mode: Cloud Native.
Integration: Identity Kore (Passport)."""
import os
import logging
import importlib
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_GENAI = None
_HarmCategory = None
_HarmBlockThreshold = None


def _load_genai():
    global _GENAI, _HarmCategory, _HarmBlockThreshold
    if _GENAI is None:
        _GENAI = importlib.import_module("google.generativeai")
        types_mod = importlib.import_module("google.generativeai.types")
        _HarmCategory = types_mod.HarmCategory
        _HarmBlockThreshold = types_mod.HarmBlockThreshold
    return _GENAI, _HarmCategory, _HarmBlockThreshold

# Importiruem Lichnost
try:
    from modules.memory import passport
except ImportError:
    passport = None

log = logging.getLogger(__name__)

class GeminiProvider:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        # By default we take 1.5 Flash (fast) or Pro.
        # If you really have 2.0/2.5 (Early Access), enter the exact model name in .env
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        if not self.api_key:
            log.warning("[Gemini] API Key not found in .env (GOOGLE_API_KEY)")
            self.model = None
            return

        try:
            genai, _, _ = _load_genai()
            genai.configure(api_key=self.api_key)
            self.model = None # Initializes lazily on first request or system prompt updates
            log.info(f"[Gemini] Configured for model: {self.model_name}")
        except Exception as e:
            log.error(f"[Gemini] Init failed: {e}")
            self.model = None

    def _get_identity_prompt(self) -> str:
        """We pull the personality from the profile."""
        if passport:
            return passport.get_identity()
        return "Ty — Ester. Your owner — Owner."

    def generate(
        self, 
        prompt: str, 
        system_prompt: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 2048, # Gemini lyubit limity
        **kwargs
    ) -> str:
        if not self.api_key:
            return "[ERROR] Gemini API Key is missing."
        try:
            genai, HarmCategory, HarmBlockThreshold = _load_genai()
        except Exception as e:
            return f"[ERROR] Gemini: google.generativeai missing ({e})"

        # 1. We create a system instruction
        # If the special prompt (for example, for summarization) - take it.
        # Otherwise, we take the Personality of Esther.
        current_sys_instruction = system_prompt if system_prompt else self._get_identity_prompt()

        try:
            # Creating a generation configuration
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens if max_tokens > 0 else 8192,
            )

            # Security settings (so that it does not block normal discussions)
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            }

            # Initsializiruem model s sistemnym promptom
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=current_sys_instruction
            )

            # Generatsiya
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            if response.text:
                return response.text
            else:
                return "[Gemini] Empty response (vozmozhno, srabotal Safety Filter)"

        except Exception as e:
            log.error(f"[Gemini] Generation error: {e}")
            return f"[ERROR] Gemini: {e}"

    def smoketest(self) -> str:
        if not self.api_key:
            return "FAILED: No API Key"
        try:
            # Bystryy test
            genai, _, _ = _load_genai()
            m = genai.GenerativeModel('gemini-1.5-flash')
            res = m.generate_content("Ping")
            return f"OK (Gemini Access Confirmed)"
        except Exception as e:
            return f"FAILED: {e}"

# Singlton
adapter = GeminiProvider()

# Compatibility wrapper
def generate(prompt, system_prompt="", **kwargs):
    return adapter.generate(prompt, system_prompt, **kwargs)