# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


class CardsMemory:
    """
    Kartochki znaniy po polzovatelyam. Format fayla: JSON {"users": {user: [cards...]}}
    Kartochka: {id, text, tags[], weight, pinned, mtime}
    """

    def __init__(self, path: Optional[str] = None):
        base = os.getenv("PERSIST_DIR") or os.path.abspath(os.path.join(os.getcwd(), "data"))
        self.path = str(path or os.path.join(base, "ester_cards.json"))
        d = os.path.dirname(os.path.abspath(self.path))
        if d:
            os.makedirs(d, exist_ok=True)
        self.data: Dict[str, Any] = {"users": {}}
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self.path):
            try:
                self.data = json.load(open(self.path, "r", encoding="utf-8"))
            except Exception:
                self.data = {"users": {}}

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list_cards(self, user: str) -> List[Dict[str, Any]]:
        return list(self.data.get("users", {}).get(user, []))

    def add_card(
        self,
        user: Optional[str] = None,
        text: Optional[str] = None,
        tags=None,
        weight: float = 0.5,
        pinned: bool = False,
        header: Optional[str] = None,
        body: Optional[str] = None,
        **_: Any,
    ) -> str:
        uid = str(user or "default")
        txt = str(text or "").strip()
        if not txt:
            parts = [str(x).strip() for x in (header, body) if str(x or "").strip()]
            txt = "\n".join(parts).strip()
        card = {
            "id": uuid.uuid4().hex,
            "text": txt,
            "tags": list(tags or []),
            "weight": float(weight),
            "pinned": bool(pinned),
            "mtime": time.time(),
        }
        self.data.setdefault("users", {}).setdefault(uid, []).append(card)
        self._save()
        return str(card["id"])
