# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

from .types import Dot, Item, LwwEntry, VectorClock
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class LwwSet:
    peer_id: str
    clock: int = 0
    entries: Dict[str, LwwEntry] = None  # id -> entry

    def __post_init__(self):
        if self.entries is None:
            self.entries = {}

    # --- lokalnye operatsii ---
    def _tick(self) -> int:
        self.clock += 1
        return self.clock

    def add(self, item: Item) -> Dot:
        d = Dot(self.peer_id, self._tick())
        e = self.entries.get(item.id) or LwwEntry(item=item)
        e.item = item
        if e.add is None or (d.ts > e.add.ts) or (d.ts == e.add.ts and d.peer > e.add.peer):
            e.add = d
        self.entries[item.id] = e
        return d

    def remove(self, item_id: str) -> Dot:
        d = Dot(self.peer_id, self._tick())
        e = self.entries.get(item_id)
        if e is None:
            e = LwwEntry(item=Item(id=item_id, payload={}))
        if e.rem is None or (d.ts > e.rem.ts) or (d.ts == e.rem.ts and d.peer > e.rem.peer):
            e.rem = d
        self.entries[item_id] = e
        return d

    # --- export/import of events (operate with “bold” dots) ---
    def export_ops(self, since_clock: Optional[int] = None) -> Iterable[Tuple[str, str, dict]]:
        """Vozvraschaet generator operatsiy: (op, item_id, data)
        op: 'add' | 'rem'
        data: {dot:{peer,ts}, payload?}
        Esli zadan since_clock — otbiraem tolko sobytiya lokalnogo pira posle etogo schetchika."""
        for item_id, e in self.entries.items():
            if e.add and (
                since_clock is None or (e.add.peer == self.peer_id and e.add.ts > since_clock)
            ):
                yield "add", item_id, {
                    "dot": {"peer": e.add.peer, "ts": e.add.ts},
                    "payload": e.item.payload,
                }
            if e.rem and (
                since_clock is None or (e.rem.peer == self.peer_id and e.rem.ts > since_clock)
            ):
                yield "rem", item_id, {"dot": {"peer": e.rem.peer, "ts": e.rem.ts}}

    def import_op(self, op: str, item_id: str, data: dict) -> None:
        e = self.entries.get(item_id) or LwwEntry(
            item=Item(id=item_id, payload=data.get("payload") or {})
        )
        if op == "add":
            dot = Dot(data["dot"]["peer"], int(data["dot"]["ts"]))
            # update the payload to a more recent one
            if data.get("payload"):
                e.item = Item(id=item_id, payload=data["payload"])
            if (
                e.add is None
                or (dot.ts > e.add.ts)
                or (dot.ts == e.add.ts and dot.peer > e.add.peer)
            ):
                e.add = dot
        elif op == "rem":
            dot = Dot(data["dot"]["peer"], int(data["dot"]["ts"]))
            if (
                e.rem is None
                or (dot.ts > e.rem.ts)
                or (dot.ts == e.rem.ts and dot.peer > e.rem.peer)
            ):
                e.rem = dot
        else:
            raise ValueError(f"unknown op {op}")
        self.entries[item_id] = e

    # --- merdzh ---
    def merge(self, other: "LwwSet") -> None:
        for item_id, e2 in other.entries.items():
            e1 = self.entries.get(item_id)
            if e1 is None:
                self.entries[item_id] = e2
                continue
            # pick latest add
            if e2.add and (
                e1.add is None
                or (e2.add.ts > e1.add.ts)
                or (e2.add.ts == e1.add.ts and e2.add.peer > e1.add.peer)
            ):
                e1.add = e2.add
                e1.item = e2.item
            # pick latest rem
            if e2.rem and (
                e1.rem is None
                or (e2.rem.ts > e1.rem.ts)
                or (e2.rem.ts == e1.rem.ts and e2.rem.peer > e1.rem.peer)
            ):
                e1.rem = e2.rem
            self.entries[item_id] = e1
        # logical clock - maximum (for local export filters)
        self.clock = max(self.clock, other.clock)

    def visible_items(self) -> Dict[str, Item]:
        return {iid: e.item for iid, e in self.entries.items() if e.visible()}

    # --- snapshot ---
    def snapshot(self) -> Dict[str, Any]:
        return {
            "peer": self.peer_id,
            "clock": self.clock,
            "entries": {
                iid: {
                    "item": {"id": e.item.id, "payload": e.item.payload},
                    "add": ({"peer": e.add.peer, "ts": e.add.ts} if e.add else None),
                    "rem": ({"peer": e.rem.peer, "ts": e.rem.ts} if e.rem else None),
                }
                for iid, e in self.entries.items()
            },
        }

    @classmethod
    def from_snapshot(cls, data: Dict[str, Any]) -> "LwwSet":
        s = cls(peer_id=data.get("peer") or "unknown", clock=int(data.get("clock") or 0))
        for iid, ed in (data.get("entries") or {}).items():
            e = LwwEntry(
                item=Item(id=ed["item"]["id"], payload=ed["item"].get("payload") or {}),
                add=(Dot(ed["add"]["peer"], int(ed["add"]["ts"])) if ed.get("add") else None),
                rem=(Dot(ed["rem"]["peer"], int(ed["rem"]["ts"])) if ed.get("rem") else None),
            )
            s.entries[iid] = e
        return s
