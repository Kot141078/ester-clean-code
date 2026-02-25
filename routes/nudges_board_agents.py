# -*- coding: utf-8 -*-
"""routes/nudges_board_agents.py - agregaty nudges po agentam (dlya “shakhmatki roley”).

MOSTY:
- (Yavnyy) GET /board/nudges/agents → [{agent_id, key, pending, overdue}].
- (Skrytyy #1) Svyazka agent→key beretsya iz nudges_recipients; statistika - iz nudges_pending (status='new').
- (Skrytyy #2) JSON kompaktnyy i samostoyatelnyy - mozhno zabirat iz fronta bordy bez pravok ostalnykh ruchek.

ZEMNOY ABZATs:
Ryadom s kazhdym operatorom mozhno pokazat prostuyu “plashku”: skolko napominaniy visit i skolko uzhe prosrocheno.

# c=a+b"""
from __future__ import annotations

import time
from typing import List, Dict, Any
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from nudges.store import _conn as _nudges_conn
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

router = APIRouter()

@router.get("/board/nudges/agents")
async def nudges_agents():
    now = time.time()
    out: List[Dict[str, Any]] = []
    with _nudges_conn() as c:
        maps = c.execute("SELECT agent_id, contact_key FROM nudges_recipients").fetchall()
        for agent_id, key in maps:
            total = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND key=?", (key,)).fetchone()[0]
            over  = c.execute("SELECT COUNT(*) FROM nudges_pending WHERE status='new' AND key=? AND due_ts<?", (key, now)).fetchone()[0]
            out.append({"agent_id": str(agent_id), "key": str(key), "pending": int(total or 0), "overdue": int(over or 0)})
    return JSONResponse({"ok": True, "ts": int(now), "agents": out})

def mount_nudges_board_agents(app: FastAPI) -> None:
    app.include_router(router)


def register(app):
    app.include_router(router)
    return app