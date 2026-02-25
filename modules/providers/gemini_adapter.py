# gemini_adapter.py
#
# A simple adapter for Gemini via the Generative Language API.
# It does one thing: accepts messages in OpenAI format, sends them to
# https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
# i vozvraschaet tekst pervogo kandidata.
#
# Podderzhivaet:
#   GEMINI_API_KEY   – klyuch
#   GEMINI_MODEL – model id (default is gemini-2.5-flush)
#
# Eksportiruet dve funktsii:
#   chat(messages, **kwargs)
#   chat_completion(messages, **kwargs)
#
# To avoid breaking the old code, chat_completes just calls chat.

import os
import logging
from typing import List, Dict, Any, Optional

import requests
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

log = logging.getLogger(__name__)

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Basic API URL (v1beta, as in your successful test)
_GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiConfigError(RuntimeError):
    """Gemini configuration error (no key, etc.)."""


def _build_url(model: Optional[str] = None) -> str:
    m = (model or GEMINI_MODEL or "gemini-2.5-flash").strip()
    return _GEMINI_ENDPOINT_TEMPLATE.format(model=m)


def _ensure_api_key() -> str:
    if not GEMINI_API_KEY:
        raise GeminiConfigError("GEMINI_API_KEY ne zadan v okruzhenii")
    return GEMINI_API_KEY


def _messages_to_text(messages: List[Dict[str, Any]]) -> str:
    """A very simple converter of a list of messages into one text.
    This will be enough for you/dialogues."""
    chunks: List[str] = []
    for m in messages or []:
        role = m.get("role") or ""
        content = m.get("content") or ""
        if not isinstance(content, str):
            # Just in case leads to the line
            content = str(content)

        # You can make a slightly more “human” format
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
    """Low level Gemini challenge.
    Returns the clean text of the first candidate or throws an exception."""
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
        # In the new Geminis this is usually max_output_tukens
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
            raise RuntimeError(f"Empty candidate list in Gemini response: ZZF0Z")

        first = candidates[0]
        content = first.get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            raise RuntimeError(f"Empty part in Gemini's response: ZZF0Z")

        text_out = parts[0].get("text")
        if not isinstance(text_out, str):
            raise RuntimeError(f"Failed to extract text from Gemini response: ZZF0Z")

        return text_out.strip()
    except Exception:
        # We log the full response so that we can debug it
        log.exception("Unexpected Gemini response format: ZZF0Z", data)
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
    """The main function that the provider.po should call."""
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
    """Synonym for chat in case provider.po uses the old name."""
    return chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        **kwargs,
    )