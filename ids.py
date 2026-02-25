# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import uuid
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# You can leave the default or pass yours through config/.env
DEFAULT_NAMESPACE = "6a2f2b14-12d7-4f20-b50e-2e7b7b8a4a1d"


def _ns(namespace_uuid: Optional[str]) -> uuid.UUID:
    """Bezopasno prevraschaem strokovyy UUID v obekt UUID (s defoltom)."""
    return uuid.UUID(namespace_uuid or DEFAULT_NAMESPACE)


def _sha256(text: str) -> str:
    """SNA-256 in hex without unnecessary magic."""
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def generate_entry_id(namespace_uuid: str, user: str, ts_iso: str, query: str, answer: str) -> str:
    """Generiruet stabilnyy determinirovannyy ID zapisi pamyati.
    Klyuch = user | ts_iso | sha256(query + '\n' + answer), v prostranstve UUIDv5.

    VAZhNO: ne ispolzuem bekslesh vnutri vyrazheniya f-stroki."""
    # We assemble the payload outside the f-line so that there is no backlash in ZZF0Z
    payload = (query or "").strip() + "\n" + (answer or "").strip()
    digest = _sha256(payload)
    key = f"{user}|{ts_iso}|{digest}"
# return str(uuid.uuid5(_ns(namespace_uuid), key))