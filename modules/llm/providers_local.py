# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class LocalProvider:
    """
    Prosteyshiy oflayn-otvetchik bez vneshnikh HTTP-zvonkov.
    Ispolzuetsya kak fallback, kogda LM Studio nedostupen.
    """
    name = "local"

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def health(self) -> Dict[str, Any]:
        return {"ok": True, "provider": self.name}

    def chat(self, message: str, history: List[Dict[str, Any]] | None = None, **kwargs: Any) -> str:
        msg = (message or "").strip().lower()
        if not msg:
            return "Skazhi, chto nuzhno sdelat ili sprosit."
        boiler = "Prinyato. Korotkiy otvet: zavisit ot konteksta. Utochni detali."
        if any(w in msg for w in ("privet", "hello", "hi", "dobryy")):
            return "Privet! Ya na meste. Chto delaem?"
        if "kto ty" in msg:
            return "Ya lokalnyy agent «Ester». Istoriya sokhranyaetsya na diske, BZ — po flagu RAG. Chem pomoch?"
        return boiler