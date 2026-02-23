# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

VectorClock = Dict[str, int]  # peer_id -> logical counter


@dataclass(frozen=True)
class Item:
    id: str
    payload: Dict[
        str, Any
    ]  # proizvolnye polya pamyati (topic, text, vectors, refs)


@dataclass(frozen=True)
class Dot:
    peer: str
    ts: int  # monotonnyy logicheskiy schetchik po piru


@dataclass
class LwwEntry:
    item: Item
    add: Optional[Dot] = None
    rem: Optional[Dot] = None

    def visible(self) -> bool:
        if self.add is None:
            return False
        if self.rem is None:
            return True
        # LWW: bolee «pozdnyaya» operatsiya pobezhdaet (po ts; pri ravenstve — peer id)
        if self.add.ts > self.rem.ts:
            return True
        if self.add.ts < self.rem.ts:
            return False
        return self.add.peer > self.rem.peer
