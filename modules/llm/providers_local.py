# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class LocalProvider:
    """The simplest offline responder without external HTTP calls.
    Used as a fake when LM Studio is not available."""
    name = "local"

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def health(self) -> Dict[str, Any]:
        return {"ok": True, "provider": self.name}

    def chat(self, message: str, history: List[Dict[str, Any]] | None = None, **kwargs: Any) -> str:
        msg = (message or "").strip().lower()
        if not msg:
            return "Tell me what needs to be done or asked."
        boiler = "Accepted. The short answer is: it depends on the context. Check the details."
        if any(w in msg for w in ("privet", "hello", "hi", "dobryy")):
            return "Hello! I'm there. What are we doing?"
        if "kto ty" in msg:
            return "I'm local agent Esther. The history is saved on disk, the knowledge base is saved using the RAG flag. How can I help?"
        return boiler