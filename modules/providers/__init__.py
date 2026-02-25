# -*- coding: utf-8 -*-
"""modules/providers/__init__.py - edinyy vkhod k provayderam LLM/Embeddings.

Tseli:
- edinyy standart vyzova (send_chat / send_embeddings);
- registry, chtoby ostalnoy kod ne zavisel ot konkretnykh SDK;
- A/B rezhimy: A = tolko lokalnye/proveryaemye vyzovy; B = dopuskaet rashirniya po env.

Mosty:
- Yavnyy (Kibernetika ↔ Inzheneriya): edinaya tochka upravleniya vkhodom/vykhodom “regulyatora”.
- Skrytyy 1 (Logika ↔ Sovmestimost): interfeys otdelen ot realizatsiy (zamena adaptera bez kaskada pravok).
- Skrytyy 2 (Infoteoriya ↔ Stoimost): obschiy parameter k/limits pozvolyaet derzhat “kanal” pod kontrolem.

Zemnoy abzats:
Eto kak perekhodnik v elektroschite: rozetok mnogo, no u tebya odin standart, chtoby ne peretykat
provoda v stene kazhdyy raz, kogda menyaetsya instrument.

# c=a+b"""

from __future__ import annotations

import importlib
import hashlib
import math
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# -------------------------
# Tipy i kontrakt
# -------------------------

@dataclass
class ProviderResult:
    ok: bool
    text: str = ""
    reply: str = ""
    provider: str = ""
    model: str = ""
    raw: Any = None
    error: str = ""
    meta: Dict[str, Any] = None  # type: ignore[assignment]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "text": self.text,
            "reply": self.reply or self.text,
            "provider": self.provider,
            "model": self.model,
            "raw": self.raw,
            "error": self.error,
            "meta": self.meta or {},
        }


class ChatProvider(Protocol):
    name: str

    def send_chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, **kwargs: Any) -> ProviderResult:
        return _fallback_chat_result(messages, model=model, provider=getattr(self, "name", "chat_provider"))

    # embeddings — optsionalno
    def send_embeddings(self, texts: List[str], model: Optional[str] = None, **kwargs: Any) -> Any:
        return _fallback_embeddings(texts, model=model, provider=getattr(self, "name", "chat_provider"))


# -------------------------
# Registry
# -------------------------

_REGISTRY: Dict[str, Callable[[], ChatProvider]] = {}


def register(name: str, factory: Callable[[], ChatProvider]) -> None:
    _REGISTRY[name.lower().strip()] = factory


def list_providers() -> List[str]:
    return sorted(_REGISTRY.keys())


def get_provider(name: Optional[str] = None) -> ChatProvider:
    key = (name or os.getenv("ESTER_PROVIDER", "lmstudio")).lower().strip()
    if key not in _REGISTRY:
        # Lazy import of known adapters (no loops)
        _lazy_autoregister()

    if key not in _REGISTRY:
        raise RuntimeError(f"provider_not_registered: {key} (available={list_providers()})")
    return _REGISTRY[key]()


def _lazy_autoregister() -> None:
    # you can add adapters here without editing the rest of the code
    # LM Studio / OpenAI-compat (lokalnyy)
    try:
        importlib.import_module("modules.providers.lmstudio_adapter")
    except Exception:
        pass


def _normalized_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "user").strip() or "user"
        content = str(m.get("content") or "").strip()
        out.append({"role": role, "content": content})
    return out


def _fallback_chat_result(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    provider: str = "fallback",
    error: str = "",
) -> ProviderResult:
    rows = _normalized_messages(messages)
    user_chunks = [str(m.get("content") or "").strip() for m in rows if str(m.get("role") or "").lower() == "user"]
    seed = user_chunks[-1] if user_chunks else (rows[-1].get("content", "") if rows else "")
    digest = hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
    preview = (seed or "(empty)").strip().replace("\n", " ")
    if len(preview) > 220:
        preview = preview[:219] + "…"
    text = f"[local-fallback:{digest}] {preview}"
    return ProviderResult(
        ok=True,
        text=text,
        reply=text,
        provider=str(provider or "fallback"),
        model=str(model or "hash-chat-v1"),
        error=str(error or ""),
        meta={"fallback": True, "digest": digest},
    )


def _hash_vector(text: str, dim: int) -> List[float]:
    vec = [0.0] * max(1, int(dim))
    src = str(text or "").encode("utf-8", errors="ignore")
    if not src:
        src = b" "
    blocks = (len(vec) + 31) // 32
    for i in range(blocks):
        chunk = hashlib.sha256(src + b":" + str(i).encode("ascii")).digest()
        for j, b in enumerate(chunk):
            idx = i * 32 + j
            if idx >= len(vec):
                break
            vec[idx] = (float(b) / 255.0) - 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [float(v / norm) for v in vec]


def _fallback_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    provider: str = "fallback",
    dim: int = 64,
    error: str = "",
) -> Dict[str, Any]:
    rows = [str(x or "") for x in (texts or [])]
    data = [{"index": i, "embedding": _hash_vector(t, dim)} for i, t in enumerate(rows)]
    return {
        "ok": True,
        "provider": str(provider or "fallback"),
        "model": str(model or f"hash-vec-{dim}"),
        "data": data,
        "error": str(error or ""),
        "meta": {"fallback": True, "dim": int(dim)},
    }


# -------------------------
# Vysokourovnevye khelpery
# -------------------------

def send_chat(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Universal chat call.
    Returns dist to be compatible with Esther's old code."""
    try:
        p = get_provider(provider)
        res = p.send_chat(messages, model=model, **kwargs)
        if isinstance(res, ProviderResult):
            return res.as_dict()
        if isinstance(res, dict):
            return dict(res)
        return _fallback_chat_result(messages, model=model, provider=getattr(p, "name", "provider")).as_dict()
    except Exception as e:
        return _fallback_chat_result(messages, model=model, provider=str(provider or "fallback"), error=f"{e.__class__.__name__}: {e}").as_dict()


def send_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    *,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Universal call embeddings (if supported)."""
    try:
        p = get_provider(provider)
        fn = getattr(p, "send_embeddings", None)
        if callable(fn):
            out = fn(texts, model=model, **kwargs)
            if out is not None:
                return out
        return _fallback_embeddings(texts, model=model, provider=getattr(p, "name", "provider"), dim=int(kwargs.get("dim", 64)))
    except Exception as e:
        return _fallback_embeddings(texts, model=model, provider=str(provider or "fallback"), dim=int(kwargs.get("dim", 64)), error=f"{e.__class__.__name__}: {e}")
