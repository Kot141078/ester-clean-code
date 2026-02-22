# -*- coding: utf-8 -*-
"""
modules/selfmanage/health.py — bazovye health-proby Ester.

MOSTY:
- (Yavnyy) check_db(), check_http_paths(), check_internal() — edinyy format HealthStatus.
- (Skrytyy #1) Avtokonfig po ENV: SELF_HEALTH_DB, SELF_HEALTH_HTTP_PROBE.
- (Skrytyy #2) Legkaya degradatsiya: oshibki ne vzryvayut protsess, vozvraschayut status="warn"/"fail" s reason.

ZEMNOY ABZATs:
Daet bystryy otvet: «zhivy li BD/routy/vnutrennie komponenty?». Podkhodit dlya cron/CI i watchdog.

# c=a+b
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from modules.synergy.store import AssignmentStore
from modules.synergy.plan_cache import CACHE
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@dataclass
class HealthStatus:
    name: str
    status: str  # ok|warn|fail
    reason: str = ""
    took_ms: int = 0
    meta: Dict[str, Any] = None  # noqa: WPS110


def _ok(name: str, took_ms: int, **meta) -> HealthStatus:
    return HealthStatus(name=name, status="ok", took_ms=took_ms, meta=meta)


def _warn(name: str, took_ms: int, reason: str, **meta) -> HealthStatus:
    return HealthStatus(name=name, status="warn", reason=reason, took_ms=took_ms, meta=meta)


def _fail(name: str, took_ms: int, reason: str, **meta) -> HealthStatus:
    return HealthStatus(name=name, status="fail", reason=reason, took_ms=took_ms, meta=meta)


def check_db() -> HealthStatus:
    t0 = time.monotonic()
    try:
        s = AssignmentStore.default()
        # prostaya operatsiya: upsert plan v testovuyu komandu i chtenie
        s.upsert_plan("__health__", {"noop": "noop"}, "trace", 0.0, 0.0)
        snap = s.get_latest_plan("__health__")
        ok = bool(snap and snap["assigned"].get("noop") == "noop")
        took = int((time.monotonic() - t0) * 1000)
        return _ok("db", took, ok=ok)
    except Exception as e:
        took = int((time.monotonic() - t0) * 1000)
        return _fail("db", took, reason=str(e))


def check_http_paths(fetch: Optional[Any] = None) -> HealthStatus:
    """
    Proveryaet lokalnye HTTP-puti (esli prilozhenie uzhe podnyato).
    ENV SELF_HEALTH_HTTP_PROBE="/health,/api/v2/health"
    """
    t0 = time.monotonic()
    paths = [p.strip() for p in os.getenv("SELF_HEALTH_HTTP_PROBE", "").split(",") if p.strip()]
    if not paths:
        return _warn("http", 0, reason="no_paths_configured")
    fetch = fetch or _default_fetch
    ok = True
    bad: List[Tuple[str, int]] = []
    for p in paths:
        try:
            code, _ = fetch("http://127.0.0.1:8080" + p)
            if code >= 300:
                ok = False
                bad.append((p, code))
        except Exception:
            ok = False
            bad.append((p, 599))
    took = int((time.monotonic() - t0) * 1000)
    if ok:
        return _ok("http", took, checked=len(paths))
    return _fail("http", took, reason=",".join(f"{p}:{c}" for p, c in bad), checked=len(paths))


def _default_fetch(url: str) -> Tuple[int, str]:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=2) as r:  # nosec - lokalnyy loopback
            return int(r.status), r.read(256).decode("utf-8", errors="ignore")
    except Exception:
        return 599, ""


def check_internal() -> HealthStatus:
    t0 = time.monotonic()
    try:
        # Proverim, chto PlanCache rabotaet (put/get)
        d = {"team": "H", "assigned": {"noop": "noop"}}
        CACHE.put_plan("health-key", d)
        back = CACHE.get_plan("health-key")
        took = int((time.monotonic() - t0) * 1000)
        if back and back.get("team") == "H":
            return _ok("internal", took)
        return _fail("internal", took, reason="plan-cache-miss")
    except Exception as e:
        took = int((time.monotonic() - t0) * 1000)
        return _fail("internal", took, reason=str(e))


def summary() -> Dict[str, Any]:
    statuses: List[HealthStatus] = []
    if os.getenv("SELF_HEALTH_DB", "1") == "1":
        statuses.append(check_db())
    statuses.append(check_internal())
    http_cfg = os.getenv("SELF_HEALTH_HTTP_PROBE", "").strip()
    if http_cfg:
        statuses.append(check_http_paths())
    overall = "ok"
    if any(s.status == "fail" for s in statuses):
        overall = "fail"
    elif any(s.status == "warn" for s in statuses):
        overall = "warn"
    return {
        "overall": overall,
        "items": [asdict(s) for s in statuses],
    }