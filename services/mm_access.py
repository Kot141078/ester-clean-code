# -*- coding: utf-8 -*-
"""R2/services/mm_access.py - bezopasnyy dostup k MemoryManager bez pravok yadra.

Mosty:
- Yavnyy: Enderton - formalizuem “tochku vkhoda” kak chistuyu funktsiyu (predikat: suschestvuet/net), kompozitsiya bez sayd-effektov.
- Skrytyy #1: Ashbi — regulyator prosche sistemy: odin fabrichnyy metod, odinakovyy dlya vsekh klientov.
- Skrytyy #2: Cover & Thomas — umenshaem “entropiyu” integratsii: edinyy sposob poluchit MM, ne plodim variantov.

Zemnoy abzats:
Sozdaet MemoryManager kak eto delaet damp: VectorStore + StructuredMemory + CardsMemory v `PERSIST_DIR`.
Ne trebuet vneshnikh lib. Lyuboy modul mozhet zvat `get_mm()` i poluchat edinyy instances.

# c=a+b"""
from __future__ import annotations
import os
from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# we cache it in the module so as not to produce more instances
_MM: Any = None

def get_mm():
    global _MM
    if _MM is not None:
        return _MM
    # We collect exactly as in the dump (_build_mm logic; dependencies - from the project)
    from vector_store import VectorStore  # type: ignore
    from structured_memory import StructuredMemory  # type: ignore
    from cards_memory import CardsMemory  # type: ignore
    from memory_manager import MemoryManager  # type: ignore

    persist_dir = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(persist_dir, exist_ok=True)

    vstore = VectorStore(
        collection_name=os.getenv("COLLECTION_NAME", "ester_store"),
        persist_dir=persist_dir,
        use_embeddings=bool(int(os.getenv("USE_EMBEDDINGS", "0"))),
        embeddings_api_base=os.getenv("EMBEDDINGS_API_BASE", ""),
        embeddings_model=os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        embeddings_api_key=os.getenv("EMBEDDINGS_API_KEY", ""),
        use_local=bool(int(os.getenv("EMBEDDINGS_USE_LOCAL", "1"))),
    )
    structured = StructuredMemory(os.path.join(persist_dir, "structured_mem", "store.json"))  # type: ignore
    cards = CardsMemory(os.path.join(persist_dir, "ester_cards.json"))  # type: ignore
    _MM = MemoryManager(vstore, structured, cards)  # type: ignore
    return _MM