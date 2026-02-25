# -*- coding: utf-8 -*-
"""messaging/contacts_csv.py - eksport/import kontaktov v CSV (opt-in, prefs, silence, last_outbound).

MOSTY:
- (Yavnyy) export_contacts_csv() → bytes; import_contacts_csv(csv_bytes) → otchet o primenennykh zapisyakh.
- (Skrytyy #1) Gibkiy razdelitel CSV_DELIM (defolt ,), zaschita ot lishnikh stolbtsov, propusk pustykh strok.
- (Skrytyy #2) Import idempotenten: REPLACE/UPSERT v SQLite-khranilische i myagkaya validatsiya chisel/dat.

ZEMNOY ABZATs:
Operator bystro perenosit bazu mezhdu sredami i pravit kontakty v Excel/Google Sheets: import obratno — i vse na meste.

# c=a+b"""
from __future__ import annotations

import csv
import io
import os
import time
from typing import Dict, List

from messaging.optin_store import (
    list_contacts,
    set_optin,
    set_prefs,
    set_silence_until,
    record_outbound,
)

def _delim() -> str:
    return os.getenv("CSV_DELIM", ",")

_HEADERS = ["key","agree","rate_per_h","persona","last_out_ts","silence_until_ts"]

def export_contacts_csv() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=_delim())
    w.writerow(_HEADERS)
    for k, agree, rate, persona, last_ts, silence_until in list_contacts(100000):
        w.writerow([k, 1 if agree else 0, int(rate), persona, int(last_ts), int(silence_until)])
    return buf.getvalue().encode("utf-8")

def _to_int(x, default=0):
    try:
        return int(str(x).strip())
    except Exception:
        return default

def import_contacts_csv(csv_bytes: bytes) -> Dict[str, int]:
    s = csv_bytes.decode("utf-8", errors="ignore")
    r = csv.reader(io.StringIO(s), delimiter=_delim())
    header = next(r, None)
    if not header:
        return {"read": 0, "applied": 0, "skipped": 0}
    idx = {name: i for i, name in enumerate(header)}
    def col(name: str) -> int: return idx.get(name, -1)

    read = applied = skipped = 0
    for row in r:
        if not row or all(not (cell or "").strip() for cell in row):
            continue
        read += 1
        try:
            key = row[col("key")]
            if not key:
                skipped += 1; continue
            agree = _to_int(row[col("agree")], 0)
            rate = _to_int(row[col("rate_per_h")], 6)
            persona = (row[col("persona")] if col("persona") >= 0 else "gentle") or "gentle"
            last_ts = _to_int(row[col("last_out_ts")], 0)
            silence_ts = _to_int(row[col("silence_until_ts")], 0)
            # apply
            set_optin(key, bool(agree))
            set_prefs(key, rate, persona)
            if silence_ts > 0:
                set_silence_until(key, float(silence_ts))
            if last_ts > 0:
                record_outbound(key)
            applied += 1
        except Exception:
            skipped += 1
    return {"read": read, "applied": applied, "skipped": skipped}
