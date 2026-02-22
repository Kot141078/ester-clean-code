# gemini_adapter.py
#
# Prostoy adapter dlya Gemini cherez Generative Language API.
# Delaet odno: prinimaet messages v formate OpenAI, shlet ikh v
# https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
# i vozvraschaet tekst pervogo kandidata.
#
# Podderzhivaet:
#   GEMINI_API_KEY   – klyuch
#   GEMINI_MODEL     – id modeli (po umolchaniyu gemini-2.5-flash)
#
# Eksportiruet dve funktsii:
#   chat(messages, **kwargs)
#   chat_completion(messages, **kwargs)
#
# Chtoby staryy kod ne slomat, chat_completion prosto vyzyvaet chat.

import os
import logging
from typing import List, Dict, Any, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Bazovyy URL API (v1beta, kak v tvoem uspeshnom teste)
_GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiConfigError(RuntimeError):
    """Oshibka konfiguratsii Gemini (net klyucha i t.p.)."""


def _build_url(model: Optional[str] = None) -> str:
    m = (model or GEMINI_MODEL or "gemini-2.5-flash").strip()
    return _GEMINI_ENDPOINT_TEMPLATE.format(model=m)


def _ensure_api_key() -> str:
    if not GEMINI_API_KEY:
        raise GeminiConfigError("GEMINI_API_KEY ne zadan v okruzhenii")
    return GEMINI_API_KEY


def _messages_to_text(messages: List[Dict[str, Any]]) -> str:
    """
    Ochen prostoy konverter spiska messages v odin tekst.
    Etogo dlya judge/dialogov tebe khvatit.
    """
    chunks: List[str] = []
    for m in messages or []:
        role = m.get("role") or ""
        content = m.get("content") or ""
        if not isinstance(content, str):
            # Na vsyakiy sluchay privodim k stroke
            content = str(content)

        # Mozhno sdelat chut bolee «chelovechnyy» format
        if role == "system":
            chunks.append(f"[system]\n{content}\n")
        elif role == "user":
            chunks.append(f"[user]\n{content}\n")
        elif role == "assistant":
            chunks.append(f"[assistant]\n{content}\n")
        else:
            chunks.append(content + "\n")

    return "\n".join(chunks).strip()


def _call_gemini(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    timeout: float = 60.0,
    **_: Any,
) -> str:
    """
    Nizkourovnevyy vyzov Gemini.
    Vozvraschaet chistyy tekst pervogo kandidata ili kidaet isklyuchenie.
    """
    api_key = _ensure_api_key()
    url = _build_url(model)

    text = _messages_to_text(messages)

    body: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": float(temperature),
        },
    }

    if max_tokens is not None:
        # V novykh Gemini eto usually max_output_tokens
        body["generationConfig"]["maxOutputTokens"] = int(max_tokens)

    log.debug("Gemini request: url=%s, model=%s, len(text)=%d", url, model or GEMINI_MODEL, len(text))

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        params={"key": api_key},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    try:
        # Standartnyy format: candidates[0].content.parts[0].text
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Pustoy spisok candidates v otvete Gemini: {data!r}")

        first = candidates[0]
        content = first.get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            raise RuntimeError(f"Pustoy parts v otvete Gemini: {data!r}")

        text_out = parts[0].get("text")
        if not isinstance(text_out, str):
            raise RuntimeError(f"Ne udalos izvlech text iz otveta Gemini: {data!r}")

        return text_out.strip()
    except Exception:
        # Logiruem polnyy otvet, chtoby mozhno bylo otladit
        log.exception("Neozhidannyy format otveta Gemini: %r", data)
        raise


# --- Publichnyy API adaptera ---


def chat(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Osnovnaya funktsiya, kotoruyu dolzhen vyzyvat providers.py.
    """
    return _call_gemini(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        **kwargs,
    )


def chat_completion(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Sinonim chat na sluchay, esli v providers.py ispolzuetsya staroe imya.
    """
    return chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        **kwargs,
    )