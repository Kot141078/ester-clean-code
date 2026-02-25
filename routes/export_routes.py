# -*- coding: utf-8 -*-
"""routes/export_routes.py - CSV-eksporty (bezopasnye, bystrye).

MOSTY:
- (Yavnyy) /export/outbox.csv, /export/mail_outbox.csv, /export/roles_edges.csv.
- (Skrytyy #1) Chitaet iz obschey BD (MESSAGING_DB_PATH), ne trebuet migratsiy.
- (Skrytyy #2) Potokovaya vydacha (generator) - ne kladet pamyat.

ZEMNOY ABZATs:
Nuzhno "uvezti" logi dostavki, pisma ili graf sygrannosti - odnim klikom v CSV.

# c=a+b"""
from __future__ import annotations

import csv, io, os, sqlite3
from typing import Iterable
from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()
DB_PATH = os.getenv("MESSAGING_DB_PATH","data/messaging.db")

def _conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
    return c

def _stream_csv(rows: Iterable[tuple], header: list[str]):
    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header); yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        for r in rows:
            w.writerow([x if not isinstance(x, (bytes, bytearray)) else x.decode("utf-8","ignore") for x in r])
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)
    return StreamingResponse(gen(), media_type="text/csv")

@router.get("/export/outbox.csv")
async def export_outbox():
    with _conn() as c:
        rows = c.execute("SELECT ts,channel,chat_id,text,status,http_status,message_id FROM outbox ORDER BY ts DESC")
        return _stream_csv(rows, ["ts","channel","chat_id","text","status","http_status","message_id"])

@router.get("/export/mail_outbox.csv")
async def export_mail_outbox():
    with _conn() as c:
        rows = c.execute("SELECT ts,recipient,subject,status,smtp_code,smtp_err,message_id FROM mail_outbox ORDER BY ts DESC")
        return _stream_csv(rows, ["ts","recipient","subject","status","smtp_code","smtp_err","message_id"])

@router.get("/export/roles_edges.csv")
async def export_roles_edges():
    with _conn() as c:
        # the table is created in Roles.Edges on the first call; if it doesn't exist, it will return empty
        exists = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles_edges'").fetchone()
        if not exists:
            return _stream_csv([], ["a","b","weight","updated_ts","context_json"])
        rows = c.execute("SELECT a,b,weight,updated_ts,COALESCE(context_json,'{}') FROM roles_edges ORDER BY updated_ts DESC")
        return _stream_csv(rows, ["a","b","weight","updated_ts","context_json"])

def mount_export_routes(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app