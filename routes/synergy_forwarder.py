# -*- coding: utf-8 -*-
"""
routes/synergy_forwarder.py - integratsionnyy forvarder sobytiy Synergy:
- push: vneshnyaya sistema POST-it massiv sobytiy;
- pull: skaner cherez ukazannyy provayder (ENV SYNERGY_FORWARDER_PROVIDER) s chekpointom.

MOSTY:
- (Yavnyy) /synergy/forwarder/push i /synergy/forwarder/scan razrulivayut «kak dostat sobytiya» bez izmeneniya Synergy Store.
- (Skrytyy #1) Chekpoint khranitsya v tom zhe SQLite, chto i messaging/nudges (bez vneshnikh migratsiy).
- (Skrytyy #2) Pryamoy vyzov nudges_event() - drop-in bez setevykh krugov.

ZEMNOY ABZATs:
Est otkuda vzyat sobytiya - cherez push ili cherez vash provayder. Net - nichego ne lomaem; chekpoint garantiruet «ne zadvaivaem».

# c=a+b
"""
from __future__ import annotations

import importlib, os, time, sqlite3
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from routes.nudges_routes import nudges_event  # pryamoy vyzov obrabotchika
from nudges.store import _conn as _nudges_conn
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

# --- chekpoint (pull) ---

def _ensure_forwarder_state():
    with _nudges_conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS nudges_forwarder_state(
          id INTEGER PRIMARY KEY CHECK (id=1),
          last_ts REAL NOT NULL
        )""")
        row = c.execute("SELECT last_ts FROM nudges_forwarder_state WHERE id=1").fetchone()
        if not row:
            c.execute("INSERT INTO nudges_forwarder_state(id,last_ts) VALUES(1,0)")

def _get_last_ts() -> float:
    _ensure_forwarder_state()
    with _nudges_conn() as c:
        return float(c.execute("SELECT last_ts FROM nudges_forwarder_state WHERE id=1").fetchone()[0])

def _set_last_ts(ts: float) -> None:
    with _nudges_conn() as c:
        c.execute("UPDATE nudges_forwarder_state SET last_ts=? WHERE id=1", (float(ts),))

def _load_provider() -> Optional[Callable[[float], List[Dict[str, Any]]]]:
    spec = os.getenv("SYNERGY_FORWARDER_PROVIDER", "").strip()
    if not spec:
        return None
    try:
        mod_name, func_name = spec.split(":", 1)
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, func_name)
        return fn  # type: ignore
    except Exception:
        return None

# --- routy ---

@router.post("/synergy/forwarder/push")
async def synergy_forwarder_push(payload: Dict[str, Any]):
    """
    Prinimaet {"events":[{event_type, entity_id, ts?, payload{...}}, ...]}
    i prokidyvaet kazhdyy v /nudges/event (lokalnyy vyzov).
    """
    events = payload.get("events") or []
    ok = 0; failed = 0
    for e in events:
        res = await nudges_event(e)
        if getattr(res, "status_code", 500) == 200:
            ok += 1
        else:
            failed += 1
    return JSONResponse({"ok": True, "accepted": ok, "failed": failed})

@router.post("/synergy/forwarder/scan")
async def synergy_forwarder_scan():
    """
    Vyzyvaet provayder (esli ukazan v ENV) i prokidyvaet novye sobytiya v /nudges/event.
    Khranit chekpoint (last_ts) v lokalnoy tablitse.
    """
    provider = _load_provider()
    if not provider:
        return JSONResponse({"ok": False, "error": "no provider configured (SYNERGY_FORWARDER_PROVIDER)"}, status_code=400)
    last_ts = _get_last_ts()
    batch = provider(last_ts) or []
    accepted = 0
    for e in sorted(batch, key=lambda x: float(x.get("ts") or time.time())):
        res = await nudges_event(e)
        if getattr(res, "status_code", 500) == 200:
            accepted += 1
            last_ts = max(last_ts, float(e.get("ts") or last_ts))
    _set_last_ts(last_ts)
    return JSONResponse({"ok": True, "accepted": accepted, "last_ts": int(last_ts)})

def mount_synergy_forwarder(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app