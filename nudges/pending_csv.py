# -*- coding: utf-8 -*-
"""
nudges/pending_csv.py — eksport ocheredi pending v CSV.

MOSTY:
- (Yavnyy) export_pending_csv(limit=20000) → bytes; kolonki: id,event_id,created_ts,due_ts,key,kind,intent,status,reason.
- (Skrytyy #1) Ispolzuet pryamoy SELECT po nudges_pending, ne menyaya suschestvuyuschie API.
- (Skrytyy #2) Razdelitel sovmestim s CSV_DELIM (kak v drugikh eksportakh).

ZEMNOY ABZATs:
Snimok ocheredi — dlya audita, otladki i bystroy vygruzki v tablichnye instrumenty.

# c=a+b
"""
from __future__ import annotations

import csv, io, os, time
import sqlite3
from typing import List, Tuple

from nudges.store import _conn as _nudges_conn
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_HEADERS = ["id","event_id","created_ts","due_ts","key","kind","intent","status","reason"]

def _delim() -> str:
    return os.getenv("CSV_DELIM", ",")

def export_pending_csv(limit: int = 20000) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=_delim())
    w.writerow(_HEADERS)
    with _nudges_conn() as c:
        rows = c.execute("""
          SELECT id,event_id,created_ts,due_ts,key,kind,intent,status,COALESCE(reason,'')
            FROM nudges_pending
           ORDER BY due_ts ASC, id ASC
           LIMIT ?""", (int(limit),)).fetchall()
        for r in rows:
            w.writerow([int(r[0]), int(r[1]), int(r[2]), int(r[3]), str(r[4]), str(r[5]),
                        str(r[6]), str(r[7]), str(r[8])])
    return buf.getvalue().encode("utf-8")