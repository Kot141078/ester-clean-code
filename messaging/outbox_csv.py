# -*- coding: utf-8 -*-
"""messaging/outbox_csv.py - eksport zhurnala iskhodyaschikh v CSV.

MOSTY:
- (Yavnyy) export_outbox_csv(limit=5000) → bytes; kolonoki: id,ts,channel,chat_id,text,status,http_status,request_id.
- (Skrytyy #1) Use list_outgoing_paged() dlya predskazuemogo poryadka i obema.
- (Skrytyy #2) Razdelitel beretsya iz CSV_DELIM (sovmestimost s eksportom kontaktov).

ZEMNOY ABZATs:
Vygruzhaem iskhodyaschie - dlya otchetnosti, audita or analiza v tablichnykh instrumentakh.

# c=a+b"""
from __future__ import annotations

import csv
import io
import os
from typing import List

from messaging.outbox_store import list_outgoing_paged
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_HEADERS = ["id","ts","channel","chat_id","text","status","http_status","request_id"]

def _delim() -> str:
    return os.getenv("CSV_DELIM", ",")

def export_outbox_csv(limit: int = 5000) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=_delim())
    w.writerow(_HEADERS)
    rows = list_outgoing_paged(limit=limit, offset=0)
    for _id, ts, ch, chat, text, status, http, rid in rows:
        w.writerow([_id, int(ts), ch, chat, text, status, http, rid])
    return buf.getvalue().encode("utf-8")