# -*- coding: utf-8 -*-
"""
modules/selfmanage/playbooks.py — «garazh» samovosstanovleniya.

MOSTY:
- (Yavnyy) Playbook: spisok shagov (callable) s otchetom; vstroennye: recover-db, restart-telemetry, rotate-plan-cache.
- (Skrytyy #1) Bezopasnye shagi — ne menyayut kontrakty; rollback ne trebuetsya (idempotentnye protsedury).
- (Skrytyy #2) Myagkaya integratsiya: mozhno vyzyvat iz admin-UI/CLI bez perezapuska protsessa.

ZEMNOY ABZATs:
Kogda «chto-to poshlo ne tak» — zapuskaem zaranee prigotovlennyy stsenariy: osvezhit konnekty, ochistit kesh, pnut adaptery.

# c=a+b
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List

from modules.selfmanage.health import HealthStatus, _ok, _fail
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


StepFn = Callable[[], HealthStatus]


@dataclass
class Step:
    name: str
    fn: StepFn


@dataclass
class PlaybookReport:
    name: str
    took_ms: int
    items: List[Dict[str, Any]]
    ok: bool


class Garage:
    def __init__(self):
        self._pbs: Dict[str, List[Step]] = {}
        self._register_default()

    def _register_default(self) -> None:
        self._pbs["recover-db"] = [
            Step("db:probe", lambda: self._probe_db()),
            Step("db:refresh", lambda: self._refresh_db()),
        ]
        self._pbs["rotate-plan-cache"] = [
            Step("cache:write", lambda: self._poke_cache()),
            Step("cache:noop", lambda: _ok("cache:noop", 0)),
        ]
        self._pbs["restart-telemetry"] = [
            Step("telemetry:ping", lambda: self._telemetry_ping()),
            Step("telemetry:noop", lambda: _ok("telemetry:noop", 0)),
        ]

    # ---- steps impl ----

    def _probe_db(self) -> HealthStatus:
        from modules.selfmanage.health import check_db
        return check_db()

    def _refresh_db(self) -> HealthStatus:
        from modules.synergy.store import AssignmentStore
        t0 = time.monotonic()
        try:
            AssignmentStore.default().get_latest_plan("__garage__")
            return _ok("db:refresh", int((time.monotonic() - t0) * 1000))
        except Exception as e:
            return _fail("db:refresh", int((time.monotonic() - t0) * 1000), reason=str(e))

    def _poke_cache(self) -> HealthStatus:
        from modules.synergy.plan_cache import CACHE
        t0 = time.monotonic()
        try:
            CACHE.put_plan("__garage__", {"ok": True})
            return _ok("cache:write", int((time.monotonic() - t0) * 1000))
        except Exception as e:
            return _fail("cache:write", int((time.monotonic() - t0) * 1000), reason=str(e))

    def _telemetry_ping(self) -> HealthStatus:
        # Zdes mozhet byt vyzov k adapteram; ostavim legkiy ping
        t0 = time.monotonic()
        try:
            # Nichego ne delaem — podrazumevaetsya vneshnyaya sistema
            return _ok("telemetry:ping", int((time.monotonic() - t0) * 1000))
        except Exception as e:
            return _fail("telemetry:ping", int((time.monotonic() - t0) * 1000), reason=str(e))

    # ---- public API ----

    def run(self, name: str) -> PlaybookReport:
        if os.getenv("SELF_GARAGE_ALLOW", "1") != "1":
            return PlaybookReport(name=name, took_ms=0, items=[{"status":"fail","reason":"garage_disabled"}], ok=False)
        steps = self._pbs.get(name, [])
        t0 = time.monotonic()
        items: List[Dict[str, Any]] = []
        ok = True
        for s in steps:
            hs = s.fn()
            items.append({"step": s.name, "status": hs.status, "reason": hs.reason, "took_ms": hs.took_ms})
            if hs.status == "fail":
                ok = False
        took = int((time.monotonic() - t0) * 1000)
        return PlaybookReport(name=name, took_ms=took, items=items, ok=ok)

    def list_playbooks(self) -> List[str]:
        return sorted(self._pbs.keys())


GARAGE = Garage()