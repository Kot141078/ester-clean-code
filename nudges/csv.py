# -*- coding: utf-8 -*-
"""nudges/csv.py - eksport nudges_log v CSV (dlya audita/analitiki).

MOSTY:
- (Yavnyy) export_log_csv(limit=10000) → bytes s kolonkami id,ts,key,kind,intent,status,http_status,event_id.
- (Skrytyy #1) Razdelitel sovmestim s CSV_DELIM (kak v messaging CSV).
- (Skrytyy #2) Sortirovka po ts DESC (kak na admin-ekrane).

ZEMNOY ABZATs:
Odnoy knopkoy vygruzhaem istoriyu nudzhey i analyze ee privychnymi instruments.

# c=a+b"""
from __future__ import annotations

import csv, io, os
from nudges.store import list_log
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_HEADERS = ["id","ts","key","kind","intent","status","http_status","event_id"]

def _delim() -> str:
    return os.getenv("CSV_DELIM", ",")

def export_log_csv(limit: int = 10000) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=_delim())
    w.writerow(_HEADERS)
    rows = list_log(limit=limit)
    for _id, ts, key, kind, intent, status, http, ev in rows:
        w.writerow([_id, int(ts), key, kind, intent, status, http, ev])
    return buf.getvalue().encode("utf-8")