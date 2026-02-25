# -*- coding: utf-8 -*-
"""asgi/synergy_api_v2.py - FastAPI-prilozhenie dlya Synergy API v2.

MOSTY:
- (Yavnyy) Routy: /synergy/assign, /overrides, /roles, /policies, /outcome, /board/data, /health.
- (Skrytyy #1) Verifikatsiya HMAC cherez security/signing.py, idempotentnost po X-Request-Id (reuse orkestratora v2).
- (Skrytyy #2) Paginatsiya spiska agentov dlya bordy; otvety oshibok v format application/problem+json.

ZEMNOY ABZATs:
Chistyy, predskazuemyy API vtorogo pokoleniya - sovmestim so starym stekom i gotov k vneshnim integratsiyam.

# c=a+b"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from modules.synergy.state_store import STORE
from modules.synergy.role_model import fit_roles_ext
from modules.synergy.orchestrator_v2 import assign_v2 as orchestrator_assign_v2
from security.signing import verify_headers
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

API_PREFIX = "/api/v2"
app = FastAPI(title="Ester Synergy API v2", version="1.0.0")
router = APIRouter(prefix="/synergy", tags=["synergy"])


# --------- utility problem+json ---------
def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "detail": detail, "status": status},
        media_type="application/problem+json",
    )


async def _auth(request: Request) -> None:
    # Verify the signature (if enabled)
    raw = await request.body()
    ok, prob = verify_headers(request.method, request.url.path, raw, request.headers)
    if not ok:
        # For idempotent retries we allow replay marker and let request-id cache handle it.
        if isinstance(prob, dict) and prob.get("title") == "replay":
            return
        if not isinstance(prob, dict):
            prob = {"title": "auth_failed", "detail": "signature validation failed"}
        status = int(prob.get("status") or 401)
        prob.setdefault("status", status)
        raise HTTPException(status_code=status, detail=prob)


# --------- request/response models (thin) ---------
class AssignBody(BaseModel):
    team_id: str
    overrides: Optional[Dict[str, str]] = None
    request_id: Optional[str] = None


# --------- routy ---------
@router.post("/assign")
async def assign(body: AssignBody, request: Request, _=Depends(_auth)):
    req_id = body.request_id or request.headers.get("X-Request-Id")
    res = orchestrator_assign_v2(body.team_id, body.overrides or {}, request_id=req_id)
    if not res.get("ok"):
        return problem(400, "assign-failed", res.get("error", "failed"))
    return JSONResponse(res)


@router.post("/overrides")
async def overrides(body: Dict[str, Any], _=Depends(_auth)):
    team_id = (body.get("team_id") or "").strip()
    ov = body.get("overrides") or {}
    t = STORE.get_team(team_id)
    if not t:
        return problem(404, "team-not-found", "team_id does not exist")
    t["overrides"] = dict(ov)
    STORE._teams[team_id] = t
    return JSONResponse({"ok": True, "overrides": t["overrides"]})


@router.get("/roles")
async def roles(_=Depends(_auth)):
    agents = STORE.list_agents()
    if agents:
        roles = sorted(list(fit_roles_ext(agents[0]).keys()))
    else:
        roles = sorted(["operator", "strategist", "platform", "communicator", "observer", "mentor", "backup", "qa"])
    return JSONResponse({"ok": True, "roles": roles})


@router.get("/policies")
async def policies(_=Depends(_auth)):
    import yaml

    path = os.getenv("SYNERGY_POLICIES_PATH", "config/synergy_policies.yaml")
    data = {}
    if os.path.exists(path):
        try:
            data = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
        except Exception:
            data = {}
    return JSONResponse({"ok": True, "path": path, "policies": data})


@router.post("/outcome")
async def outcome(body: Dict[str, Any], _=Depends(_auth)):
    team_id = (body.get("team_id") or "").strip()
    outcome = (body.get("outcome") or "").strip().lower() or "success"
    notes = (body.get("notes") or "").strip()
    t = STORE.get_team(team_id)
    if not t:
        return problem(404, "team-not-found", "team_id does not exist")
    hist = t.setdefault("history", [])
    hist.append({"outcome": outcome, "notes": notes})
    STORE._teams[team_id] = t
    return JSONResponse({"ok": True, "team": team_id, "history": hist})


@router.get("/board/data")
async def board_data(team_id: str, limit: int = 100, offset: int = 0):
    team = STORE.get_team(team_id) or {}
    agents = STORE.list_agents()
    sl = agents[offset : offset + limit]
    scores = {a["id"]: fit_roles_ext(a) for a in sl}
    return JSONResponse(
        {
            "ok": True,
            "team": team,
            "agents": sl,
            "scores": scores,
            "overrides": team.get("overrides") or {},
            "assigned": team.get("assigned") or {},
            "paging": {"limit": limit, "offset": offset, "total": len(agents)},
        }
    )


@app.get("/health")
async def health():
    return {"ok": True, "service": "synergy-api-v2"}


@app.exception_handler(HTTPException)
async def _http_problem_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "title" in detail:
        status = int(detail.get("status") or exc.status_code or 400)
        payload = dict(detail)
        payload.setdefault("status", status)
        return JSONResponse(
            status_code=status,
            content=payload,
            media_type="application/problem+json",
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


# Legacy compatibility: keep old /synergy/* paths.
app.include_router(router)
# Canonical v2 paths.
app.include_router(router, prefix=API_PREFIX)
