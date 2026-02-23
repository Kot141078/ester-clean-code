# -*- coding: utf-8 -*-
"""
messaging/inbox_store.py — mini-inboks: peydzhing + servernyy filtr po kanalu.

MOSTY:
- (Yavnyy) list_recent_paged_filtered(limit, offset, channel) — SQL-filtr WHERE channel=?
- (Skrytyy #1) Prezhnie API list_recent/list_recent_paged — sokhraneny dlya sovmestimosti.
- (Skrytyy #2) Indeks po ts (iskhodnyy DDL) uskoryaet vydachu bolshikh lent.

ZEMNOY ABZATs:
Mozhno bystro prolistyvat tolko Telegram ili tolko WhatsApp — ne peregruzhaya brauzer tekstami iz drugogo kanala.

# c=a+b
"""
from __future__ import annotations

from typing import List, Tuple, Optional

from messaging.optin_store import inbox_add, inbox_list, inbox_clear, _conn
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def add_event(ts: float, channel: str, chat_id: str, user_id: Optional[str], text: str) -> None:
    inbox_add(ts, channel, str(chat_id), user_id, text)

def list_recent(limit: int = 100) -> List[Tuple[int, float, str, str, Optional[str], str]]:
    return inbox_list(limit)

def list_recent_paged(limit: int = 100, offset: int = 0) -> List[Tuple[int, float, str, str, Optional[str], str]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id,ts,channel,chat_id,user_id,text FROM inbox ORDER BY ts DESC LIMIT ? OFFSET ?",
            (int(limit), int(offset))
        ).fetchall()
    return [(int(r[0]), float(r[1]), str(r[2]), str(r[3]), (str(r[4]) if r[4] is not None else None), str(r[5])) for r in rows]

def list_recent_paged_filtered(limit: int = 100, offset: int = 0, channel: str | None = None) -> List[Tuple[int, float, str, str, Optional[str], str]]:
    if channel not in ("telegram","whatsapp",None):
        channel = None
    sql = "SELECT id,ts,channel,chat_id,user_id,text FROM inbox"
    args = []
    if channel:
        sql += " WHERE channel=?"
        args.append(channel)
    sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
    args.extend([int(limit), int(offset)])
    with _conn() as c:
        rows = c.execute(sql, tuple(args)).fetchall()
    return [(int(r[0]), float(r[1]), str(r[2]), str(r[3]), (str(r[4]) if r[4] is not None else None), str(r[5])) for r in rows]

def clear(older_than_ts: float | None = None) -> int:
    return inbox_clear(older_than_ts)